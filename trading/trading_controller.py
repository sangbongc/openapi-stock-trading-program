from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Any, Iterable


class TradingStatus(str, Enum):
    """
    자동매매 Controller의 현재 실행 상태.
    """

    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"


class TradingController:
    """
    TradingEngine, ExecutionManager, OrderManager,
    PositionManager의 실행 시점을 제어한다.

    주요 책임
    ---------
    1. 전략 실행을 일정 주기로 반복
    2. 미완료 주문의 체결 상태를 별도 주기로 동기화
    3. 자동매매 안전 시작 및 중단
    4. 전체 종목 1회 실행
    5. 수동 매수 및 매도
    6. 계좌와 보유 종목 조회
    7. 최근 실행 결과와 오류 보관

    실제 BUY / SELL / HOLD 판단은 TradingEngine이 담당하고,
    체결 상태 확인은 ExecutionManager가 담당한다.
    """

    def __init__(
        self,
        trading_engine: Any,
        execution_manager: Any,
        order_manager: Any,
        position_manager: Any,
        stock_universe: Iterable[str | dict[str, Any]],
        interval_seconds: float = 300.0,
        sync_interval_seconds: float = 10.0,
    ) -> None:
        """
        Parameters
        ----------
        trading_engine
            run_all(stocks) 메서드를 제공하는 TradingEngine

        execution_manager
            sync_open_orders(), sync_order(order_no) 메서드를
            제공하는 ExecutionManager

        order_manager
            buy(), sell() 메서드를 제공하는 OrderManager

        position_manager
            refresh(), get_all_positions(),
            get_account_summary(), validate_sell_quantity() 메서드를
            제공하는 PositionManager

        stock_universe
            자동매매 대상 종목 목록

        interval_seconds
            전체 종목 전략 실행 주기

        sync_interval_seconds
            미완료 주문 체결 동기화 주기
        """
        self._validate_dependencies(
            trading_engine=trading_engine,
            execution_manager=execution_manager,
            order_manager=order_manager,
            position_manager=position_manager,
        )

        if stock_universe is None:
            raise ValueError(
                "stock_universe는 None일 수 없습니다."
            )

        if isinstance(stock_universe, (str, bytes)):
            raise TypeError(
                "stock_universe에는 종목 목록을 전달해야 합니다."
            )

        if not isinstance(interval_seconds, (int, float)):
            raise TypeError(
                "interval_seconds는 숫자여야 합니다."
            )

        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds는 0보다 커야 합니다."
            )

        if not isinstance(
            sync_interval_seconds,
            (int, float),
        ):
            raise TypeError(
                "sync_interval_seconds는 숫자여야 합니다."
            )

        if sync_interval_seconds <= 0:
            raise ValueError(
                "sync_interval_seconds는 0보다 커야 합니다."
            )

        self.trading_engine = trading_engine
        self.execution_manager = execution_manager
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.stock_universe = list(stock_universe)

        self.interval_seconds = float(interval_seconds)
        self.sync_interval_seconds = float(
            sync_interval_seconds
        )

        self._stop_event = threading.Event()
        self._state_lock = threading.RLock()

        # 전략 실행과 체결 동기화가 동시에 계좌 API 또는
        # 주문 DB를 변경하지 못하도록 하나의 공용 Lock을 사용한다.
        self._run_lock = threading.Lock()

        self._worker_thread: threading.Thread | None = None
        self._sync_thread: threading.Thread | None = None

        self._status = TradingStatus.STOPPED

        self.last_results: list[dict[str, Any]] = []
        self.last_execution_results: list[
            dict[str, Any]
        ] = []
        self.last_error: str | None = None

    @staticmethod
    def _validate_dependencies(
        trading_engine: Any,
        execution_manager: Any,
        order_manager: Any,
        position_manager: Any,
    ) -> None:
        if trading_engine is None:
            raise ValueError(
                "trading_engine은 None일 수 없습니다."
            )

        if execution_manager is None:
            raise ValueError(
                "execution_manager는 None일 수 없습니다."
            )

        if order_manager is None:
            raise ValueError(
                "order_manager는 None일 수 없습니다."
            )

        if position_manager is None:
            raise ValueError(
                "position_manager는 None일 수 없습니다."
            )

        required_methods = (
            (trading_engine, "run_all", "trading_engine"),
            (
                execution_manager,
                "sync_open_orders",
                "execution_manager",
            ),
            (
                execution_manager,
                "sync_order",
                "execution_manager",
            ),
            (order_manager, "buy", "order_manager"),
            (order_manager, "sell", "order_manager"),
            (position_manager, "refresh", "position_manager"),
            (
                position_manager,
                "get_all_positions",
                "position_manager",
            ),
            (
                position_manager,
                "get_account_summary",
                "position_manager",
            ),
            (
                position_manager,
                "validate_sell_quantity",
                "position_manager",
            ),
        )

        for dependency, method_name, dependency_name in (
            required_methods
        ):
            if not callable(
                getattr(dependency, method_name, None)
            ):
                raise TypeError(
                    f"{dependency_name}에는 호출 가능한 "
                    f"{method_name}() 메서드가 필요합니다."
                )

    def start(self) -> dict[str, Any]:
        """
        전략 실행 스레드와 체결 동기화 스레드를 시작한다.

        전략 스레드는 interval_seconds마다 전체 종목을 실행하고,
        동기화 스레드는 sync_interval_seconds마다 미완료 주문의
        체결 상태를 조회한다.
        """
        with self._state_lock:
            if self._status == TradingStatus.RUNNING:
                return self._build_control_result(
                    success=False,
                    message="자동매매가 이미 실행 중입니다.",
                )

            if self._status == TradingStatus.STOPPING:
                return self._build_control_result(
                    success=False,
                    message=(
                        "자동매매가 현재 중단 처리 중입니다."
                    ),
                )

            self._stop_event.clear()
            self.last_error = None
            self._status = TradingStatus.RUNNING

            self._worker_thread = threading.Thread(
                target=self._trading_loop,
                name="TradingControllerWorker",
                daemon=True,
            )

            self._sync_thread = threading.Thread(
                target=self._sync_loop,
                name="TradingControllerSyncWorker",
                daemon=True,
            )

            worker_thread = self._worker_thread
            sync_thread = self._sync_thread

        try:
            worker_thread.start()
            sync_thread.start()

        except Exception as error:
            self.last_error = str(error)
            self._stop_event.set()

            with self._state_lock:
                self._status = TradingStatus.STOPPED
                self._worker_thread = None
                self._sync_thread = None

            return self._build_control_result(
                success=False,
                message=(
                    "자동매매 작업 스레드를 시작하지 "
                    f"못했습니다: {error}"
                ),
            )

        return self._build_control_result(
            success=True,
            message=(
                "자동매매를 시작했습니다. "
                f"전략 실행 {self.interval_seconds:.0f}초, "
                f"체결 동기화 {self.sync_interval_seconds:.0f}초 "
                "주기로 동작합니다."
            ),
        )

    def stop(
        self,
        wait: bool = True,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """
        전략 실행 및 체결 동기화 스레드의 중단을 요청한다.

        현재 진행 중인 API 호출은 강제로 끊지 않고,
        해당 작업이 끝난 뒤 안전하게 중단한다.
        """
        if not isinstance(wait, bool):
            raise TypeError("wait는 bool이어야 합니다.")

        if timeout is not None:
            if not isinstance(timeout, (int, float)):
                raise TypeError(
                    "timeout은 숫자 또는 None이어야 합니다."
                )

            if timeout < 0:
                raise ValueError(
                    "timeout은 0 이상이어야 합니다."
                )

        with self._state_lock:
            if self._status == TradingStatus.STOPPED:
                return self._build_control_result(
                    success=False,
                    message=(
                        "현재 자동매매가 실행 중이 아닙니다."
                    ),
                )

            self._status = TradingStatus.STOPPING
            self._stop_event.set()

            worker_thread = self._worker_thread
            sync_thread = self._sync_thread

        if wait:
            current_thread = threading.current_thread()

            if (
                worker_thread is not None
                and worker_thread is not current_thread
            ):
                worker_thread.join(timeout=timeout)

            if (
                sync_thread is not None
                and sync_thread is not current_thread
            ):
                sync_thread.join(timeout=timeout)

        with self._state_lock:
            worker_alive = (
                self._worker_thread is not None
                and self._worker_thread.is_alive()
            )
            sync_alive = (
                self._sync_thread is not None
                and self._sync_thread.is_alive()
            )

            if not worker_alive:
                self._worker_thread = None

            if not sync_alive:
                self._sync_thread = None

            if not worker_alive and not sync_alive:
                self._status = TradingStatus.STOPPED

        if worker_alive or sync_alive:
            return self._build_control_result(
                success=True,
                message=(
                    "자동매매 중단을 요청했습니다. "
                    "현재 작업이 끝나면 중단됩니다."
                ),
            )

        return self._build_control_result(
            success=True,
            message="자동매매가 중단되었습니다.",
        )

    def run_once(self) -> dict[str, Any]:
        """
        체결 동기화, 계좌 갱신, 전체 종목 전략 실행을
        한 번만 수행한다.

        반복 자동매매 중에는 중복 주문을 방지하기 위해
        별도의 1회 실행을 허용하지 않는다.
        """
        with self._state_lock:
            if self._status != TradingStatus.STOPPED:
                return self._build_control_result(
                    success=False,
                    message=(
                        "자동매매가 실행 중이거나 "
                        "중단 처리 중이므로 "
                        "1회 실행할 수 없습니다."
                    ),
                )

        if not self._run_lock.acquire(blocking=False):
            return self._build_control_result(
                success=False,
                message=(
                    "다른 매매 작업이 이미 실행 중입니다."
                ),
            )

        try:
            self.last_error = None
            cycle_result = self._run_once_cycle()

            return {
                "success": True,
                "status": self.get_status(),
                "message": (
                    "전체 종목의 1회 실행을 완료했습니다."
                ),
                **cycle_result,
            }

        except Exception as error:
            self.last_error = str(error)

            return {
                "success": False,
                "status": self.get_status(),
                "message": (
                    "1회 실행 중 오류가 발생했습니다."
                ),
                "error": self.last_error,
                "execution_results": (
                    self.last_execution_results
                ),
                "trading_results": self.last_results,
            }

        finally:
            self._run_lock.release()

    def sync(self) -> dict[str, Any]:
        """
        미완료 주문의 체결 상태만 수동으로 동기화한다.

        반복 자동매매 중에는 별도 동기화 스레드가 실행되므로
        수동 sync 명령은 허용하지 않는다.
        """
        with self._state_lock:
            if self._status != TradingStatus.STOPPED:
                return {
                    "success": False,
                    "status": self.get_status(),
                    "message": (
                        "자동매매 실행 중에는 주기적 체결 "
                        "동기화가 이미 작동하고 있습니다."
                    ),
                }

        if not self._run_lock.acquire(blocking=False):
            return {
                "success": False,
                "status": self.get_status(),
                "message": "다른 작업이 실행 중입니다.",
            }

        try:
            self.last_error = None
            execution_results = self._sync_open_orders(
                refresh_positions=True
            )

            changed = self._count_changed(
                execution_results
            )
            errors = self._count_errors(
                execution_results
            )

            return {
                "success": True,
                "status": self.get_status(),
                "message": "체결 동기화를 완료했습니다.",
                "execution_results": execution_results,
                "changed": changed,
                "errors": errors,
            }

        except Exception as error:
            self.last_error = str(error)

            return {
                "success": False,
                "status": self.get_status(),
                "message": (
                    "체결 동기화 중 오류가 "
                    f"발생했습니다: {error}"
                ),
            }

        finally:
            self._run_lock.release()

    def get_status(self) -> str:
        """
        현재 Controller 상태를 문자열로 반환한다.
        """
        with self._state_lock:
            return self._status.value

    def get_state(self) -> dict[str, Any]:
        """
        현재 상태, 작업 스레드, 실행 주기,
        최근 실행 결과를 반환한다.
        """
        with self._state_lock:
            worker_alive = (
                self._worker_thread is not None
                and self._worker_thread.is_alive()
            )
            sync_worker_alive = (
                self._sync_thread is not None
                and self._sync_thread.is_alive()
            )
            status = self._status.value

        return {
            "status": status,

            # 기존 main.py 또는 테스트와의 호환성을 위해
            # worker_alive 이름을 유지한다.
            "worker_alive": worker_alive,
            "trading_worker_alive": worker_alive,
            "sync_worker_alive": sync_worker_alive,

            "interval_seconds": self.interval_seconds,
            "sync_interval_seconds": (
                self.sync_interval_seconds
            ),
            "stock_count": len(self.stock_universe),
            "last_error": self.last_error,
            "last_execution_results": (
                self.last_execution_results
            ),
            "last_results": self.last_results,
        }

    def manual_buy(
        self,
        stock_code: str,
        quantity: int,
        order_type: str = "MARKET",
        price: int = 0,
    ) -> dict[str, Any]:
        """
        사용자가 직접 입력한 조건으로 매수 주문을 실행한다.

        전략 신호는 사용하지 않으며 OrderManager를 통해
        주문 API를 호출하고 주문 내역을 DB에 저장한다.
        """
        blocked_result = self._manual_action_blocked_result(
            action_name="수동 매수"
        )
        if blocked_result is not None:
            return blocked_result

        if not self._run_lock.acquire(blocking=False):
            return {
                "success": False,
                "status": "BLOCKED",
                "message": (
                    "다른 매매 작업이 실행 중이어서 "
                    "수동 매수할 수 없습니다."
                ),
            }

        try:
            self.last_error = None

            order_result = self.order_manager.buy(
                stock_code=stock_code,
                quantity=quantity,
                price=price,
                order_type=order_type,
            )

            return self._sync_manual_order(order_result)

        except Exception as error:
            self.last_error = str(error)

            return {
                "success": False,
                "status": "ERROR",
                "message": (
                    "수동 매수 주문 중 오류가 "
                    f"발생했습니다: {error}"
                ),
            }

        finally:
            self._run_lock.release()

    def manual_sell(
        self,
        stock_code: str,
        quantity: int,
        order_type: str = "MARKET",
        price: int = 0,
    ) -> dict[str, Any]:
        """
        사용자가 직접 입력한 조건으로 매도 주문을 실행한다.

        주문 전에 실제 계좌 보유 상태를 다시 조회하고
        매도 가능 수량을 검증한다.
        """
        blocked_result = self._manual_action_blocked_result(
            action_name="수동 매도"
        )
        if blocked_result is not None:
            return blocked_result

        if not self._run_lock.acquire(blocking=False):
            return {
                "success": False,
                "status": "BLOCKED",
                "message": (
                    "다른 매매 작업이 실행 중이어서 "
                    "수동 매도할 수 없습니다."
                ),
            }

        try:
            self.last_error = None

            self.position_manager.refresh()

            self.position_manager.validate_sell_quantity(
                stock_code=stock_code,
                quantity=quantity,
            )

            order_result = self.order_manager.sell(
                stock_code=stock_code,
                quantity=quantity,
                price=price,
                order_type=order_type,
            )

            return self._sync_manual_order(order_result)

        except Exception as error:
            self.last_error = str(error)

            return {
                "success": False,
                "status": "ERROR",
                "message": (
                    "수동 매도 주문 중 오류가 "
                    f"발생했습니다: {error}"
                ),
            }

        finally:
            self._run_lock.release()

    def get_account(self) -> dict[str, Any]:
        """
        실제 계좌 잔고를 다시 조회하고,
        계좌 요약과 현재 보유 종목을 반환한다.
        """
        if not self._run_lock.acquire(blocking=False):
            return {
                "success": False,
                "message": (
                    "다른 매매 작업이 실행 중이어서 "
                    "계좌를 조회할 수 없습니다."
                ),
                "account_summary": {},
                "positions": {},
            }

        try:
            self.last_error = None

            positions = self.position_manager.refresh()
            account_summary = (
                self.position_manager.get_account_summary()
            )

            return {
                "success": True,
                "message": "계좌 조회를 완료했습니다.",
                "account_summary": account_summary,
                "positions": positions,
            }

        except Exception as error:
            self.last_error = str(error)

            return {
                "success": False,
                "message": (
                    "계좌를 조회하는 중 오류가 "
                    f"발생했습니다: {error}"
                ),
                "account_summary": {},
                "positions": {},
            }

        finally:
            self._run_lock.release()

    def get_positions(
        self,
        refresh: bool = True,
    ) -> dict[str, Any]:
        """
        현재 보유 종목을 반환한다.
        """
        with self._state_lock:
            if self._status != TradingStatus.STOPPED:
                return {
                    "success": False,
                    "message": (
                        "반복 자동매매가 실행 중입니다. "
                        "stop 명령 후 조회하세요."
                    ),
                    "positions": {},
                }

        if not self._run_lock.acquire(blocking=False):
            return {
                "success": False,
                "message": (
                    "다른 매매 작업이 실행 중이어서 "
                    "보유 종목을 조회할 수 없습니다."
                ),
                "positions": {},
            }

        try:
            self.last_error = None

            if refresh:
                positions = self.position_manager.refresh()
            else:
                positions = (
                    self.position_manager.get_all_positions()
                )

            return {
                "success": True,
                "message": "보유 종목 조회를 완료했습니다.",
                "positions": positions,
            }

        except Exception as error:
            self.last_error = str(error)

            return {
                "success": False,
                "message": (
                    "보유 종목 조회 중 오류가 "
                    f"발생했습니다: {error}"
                ),
                "positions": {},
            }

        finally:
            self._run_lock.release()

    def shutdown(
        self,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """
        프로그램 종료 전에 두 작업 스레드를 정리한다.
        """
        with self._state_lock:
            is_stopped = (
                self._status == TradingStatus.STOPPED
            )

        if is_stopped:
            return self._build_control_result(
                success=True,
                message=(
                    "자동매매가 이미 중단된 상태입니다."
                ),
            )

        return self.stop(
            wait=True,
            timeout=timeout,
        )

    def _trading_loop(self) -> None:
        """
        전체 종목 전략 및 주문을 반복 실행한다.

        첫 전략 실행은 start 직후 수행하고,
        이후 interval_seconds 간격으로 반복한다.
        """
        failed = False

        try:
            while not self._stop_event.is_set():
                acquired = self._run_lock.acquire(
                    blocking=False
                )

                if not acquired:
                    self.last_error = (
                        "체결 동기화 또는 다른 작업이 "
                        "실행 중이어서 이번 전략 주기를 "
                        "건너뛰었습니다."
                    )

                else:
                    try:
                        self.last_error = None
                        self._run_trading_cycle()

                    except Exception as error:
                        self.last_error = str(error)

                    finally:
                        self._run_lock.release()

                if self._stop_event.wait(
                    self.interval_seconds
                ):
                    break

        except Exception as error:
            failed = True
            self.last_error = str(error)

        finally:
            if failed:
                self._stop_event.set()

            self._mark_thread_finished("trading")

    def _sync_loop(self) -> None:
        """
        미완료 주문의 체결 상태를 주기적으로 동기화한다.

        start 직후에는 전략 스레드가 먼저 주문을 생성할
        시간을 주기 위해 sync_interval_seconds만큼 기다린 뒤
        첫 동기화를 수행한다.
        """
        failed = False

        try:
            while not self._stop_event.wait(
                self.sync_interval_seconds
            ):
                acquired = self._run_lock.acquire(
                    blocking=False
                )

                if not acquired:
                    # 전략 주기나 다른 작업과 겹친 경우에는
                    # 다음 동기화 주기에 다시 시도한다.
                    continue

                try:
                    execution_results = (
                        self._sync_open_orders(
                            refresh_positions=True
                        )
                    )

                    # 정상 동기화에 성공한 경우 이전의
                    # 일시적인 오류 메시지를 제거한다.
                    if not self._count_errors(
                        execution_results
                    ):
                        self.last_error = None

                except Exception as error:
                    self.last_error = (
                        "주기적 체결 동기화 중 오류가 "
                        f"발생했습니다: {error}"
                    )

                finally:
                    self._run_lock.release()

        except Exception as error:
            failed = True
            self.last_error = str(error)

        finally:
            if failed:
                self._stop_event.set()

            self._mark_thread_finished("sync")

    def _run_once_cycle(self) -> dict[str, Any]:
        """
        수동 run 명령에서 사용할 전체 1회 실행 흐름.

        실행 순서
        ---------
        1. 기존 미완료 주문 체결 동기화
        2. 실제 계좌 포지션 갱신
        3. 전체 종목 전략 및 주문 실행
        """
        execution_results = self._sync_open_orders(
            refresh_positions=False
        )

        trading_results = self._run_trading_cycle()

        return {
            "execution_results": execution_results,
            "trading_results": trading_results,
        }

    def _run_trading_cycle(
        self,
    ) -> list[dict[str, Any]]:
        """
        실제 계좌 포지션을 갱신한 뒤 전체 종목의
        전략 및 주문을 실행한다.
        """
        self.position_manager.refresh()

        trading_results = self.trading_engine.run_all(
            self.stock_universe
        )

        if trading_results is None:
            trading_results = []

        if not isinstance(trading_results, list):
            raise TypeError(
                "TradingEngine.run_all()은 리스트를 "
                "반환해야 합니다."
            )

        self.last_results = trading_results
        return trading_results

    def _sync_open_orders(
        self,
        refresh_positions: bool,
    ) -> list[dict[str, Any]]:
        """
        미완료 주문을 동기화하고 최근 체결 결과를 저장한다.

        신규 체결 또는 상태 변경이 발생하고
        refresh_positions가 True이면 실제 계좌를 다시 조회한다.
        """
        execution_results = (
            self.execution_manager.sync_open_orders()
        )

        if execution_results is None:
            execution_results = []

        if not isinstance(execution_results, list):
            raise TypeError(
                "sync_open_orders()는 리스트를 "
                "반환해야 합니다."
            )

        self.last_execution_results = execution_results

        if (
            refresh_positions
            and self._count_changed(execution_results) > 0
        ):
            self.position_manager.refresh()

        return execution_results

    def _sync_manual_order(
        self,
        order_result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        수동 주문이 정상 접수된 경우 체결 상태를 조회한다.

        증권사 주문조회 반영 지연을 고려해
        1.5초 간격으로 최대 두 번 확인한다.
        """
        if not isinstance(order_result, dict):
            raise TypeError(
                "OrderManager의 주문 결과는 "
                "dict여야 합니다."
            )

        accepted = bool(
            order_result.get("ACCEPTED")
            or order_result.get("accepted")
        )

        if not accepted:
            return order_result

        order_no = str(
            order_result.get("order_no") or ""
        ).strip()

        if not order_no:
            order_result["execution_sync"] = None
            order_result["execution_sync_error"] = (
                "주문번호가 없어 체결 상태를 "
                "동기화하지 못했습니다."
            )
            return order_result

        last_execution_result: dict[str, Any] | None = None
        last_error: str | None = None

        for attempt in range(2):
            time.sleep(1.5)

            try:
                execution_result = (
                    self.execution_manager.sync_order(
                        order_no
                    )
                )

                if not isinstance(execution_result, dict):
                    raise TypeError(
                        "sync_order()는 dict를 "
                        "반환해야 합니다."
                    )

                last_execution_result = execution_result
                last_error = None

                execution_status = str(
                    execution_result.get(
                        "execution_status",
                        "PENDING",
                    )
                ).upper()

                if execution_status in {
                    "FILLED",
                    "PARTIAL",
                    "PARTIALLY_FILLED",
                    "CANCELLED",
                    "REJECTED",
                }:
                    break

            except Exception as error:
                last_error = str(error)

                if attempt == 1:
                    break

        order_result["execution_sync"] = (
            last_execution_result
        )
        order_result["execution_sync_error"] = last_error

        if last_execution_result is not None:
            self.last_execution_results = [
                last_execution_result
            ]

            if last_execution_result.get("changed"):
                try:
                    self.position_manager.refresh()
                except Exception as error:
                    order_result[
                        "position_refresh_error"
                    ] = str(error)

        return order_result

    def _manual_action_blocked_result(
        self,
        action_name: str,
    ) -> dict[str, Any] | None:
        """
        반복 자동매매 중 수동 주문을 차단한다.
        """
        with self._state_lock:
            if self._status == TradingStatus.STOPPED:
                return None

            return {
                "success": False,
                "status": "BLOCKED",
                "message": (
                    "반복 자동매매가 실행 중입니다. "
                    f"stop 명령 후 {action_name}를 "
                    "실행하세요."
                ),
            }

    def _mark_thread_finished(
        self,
        thread_type: str,
    ) -> None:
        """
        작업 스레드 종료 상태를 기록한다.

        두 스레드가 모두 종료된 경우에만 Controller 상태를
        STOPPED로 변경한다.
        """
        with self._state_lock:
            if thread_type == "trading":
                self._worker_thread = None

            elif thread_type == "sync":
                self._sync_thread = None

            else:
                raise ValueError(
                    f"알 수 없는 스레드 종류입니다: {thread_type}"
                )

            if (
                self._worker_thread is None
                and self._sync_thread is None
            ):
                self._status = TradingStatus.STOPPED
                self._stop_event.set()

    @staticmethod
    def _count_changed(
        execution_results: list[dict[str, Any]],
    ) -> int:
        return sum(
            1
            for result in execution_results
            if isinstance(result, dict)
            and bool(result.get("changed"))
        )

    @staticmethod
    def _count_errors(
        execution_results: list[dict[str, Any]],
    ) -> int:
        return sum(
            1
            for result in execution_results
            if isinstance(result, dict)
            and str(
                result.get("execution_status", "")
            ).upper()
            == "ERROR"
        )

    def _build_control_result(
        self,
        success: bool,
        message: str,
    ) -> dict[str, Any]:
        """
        start, stop, shutdown의 반환 형식을 통일한다.
        """
        return {
            "success": success,
            "status": self.get_status(),
            "message": message,
            "last_error": self.last_error,
        }