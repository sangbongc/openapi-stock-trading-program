from __future__ import annotations

import threading
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
    TradingEngine과 ExecutionManager의 실행 시점과
    반복 동작을 제어한다.

    주요 책임
    ---------
    1. 자동매매 반복 실행 시작
    2. 자동매매 안전 중단
    3. 전체 종목 1회 실행
    4. 기존 미체결 주문 동기화
    5. 최근 실행 결과와 오류 보관

    실제 BUY / SELL / HOLD 판단은 TradingEngine이 담당하며,
    체결 상태 확인은 ExecutionManager가 담당한다.
    """

    def __init__(
        self,
        trading_engine: Any,
        execution_manager: Any,
        stock_universe: Iterable[str | dict[str, Any]],
        interval_seconds: float = 300.0,
    ) -> None:
        """
        Parameters
        ----------
        trading_engine
            run_all(stocks) 메서드를 제공하는 TradingEngine

        execution_manager
            sync_open_orders() 메서드를 제공하는 ExecutionManager

        stock_universe
            자동매매 대상 종목 목록

        interval_seconds
            전체 자동매매 주기의 반복 간격
        """
        if trading_engine is None:
            raise ValueError(
                "trading_engine은 None일 수 없습니다."
            )

        if execution_manager is None:
            raise ValueError(
                "execution_manager는 None일 수 없습니다."
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

        if not callable(
            getattr(trading_engine, "run_all", None)
        ):
            raise TypeError(
                "trading_engine에는 호출 가능한 "
                "run_all() 메서드가 필요합니다."
            )

        if not callable(
            getattr(
                execution_manager,
                "sync_open_orders",
                None,
            )
        ):
            raise TypeError(
                "execution_manager에는 호출 가능한 "
                "sync_open_orders() 메서드가 필요합니다."
            )

        self.trading_engine = trading_engine
        self.execution_manager = execution_manager
        self.stock_universe = list(stock_universe)
        self.interval_seconds = float(interval_seconds)

        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._state_lock = threading.RLock()
        self._run_lock = threading.Lock()

        self._status = TradingStatus.STOPPED

        self.last_results: list[dict[str, Any]] = []
        self.last_execution_results: list[
            dict[str, Any]
        ] = []
        self.last_error: str | None = None

    def start(self) -> dict[str, Any]:
        """
        별도 작업 스레드에서 자동매매 반복 실행을 시작한다.

        이미 실행 중이거나 중단 처리 중이면
        새로운 작업 스레드를 생성하지 않는다.
        """
        with self._state_lock:
            if self._status == TradingStatus.RUNNING:
                return self._build_control_result(
                    success=False,
                    message=(
                        "자동매매가 이미 실행 중입니다."
                    ),
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

            self._worker_thread.start()

        return self._build_control_result(
            success=True,
            message="자동매매를 시작했습니다.",
        )

    def stop(
        self,
        wait: bool = True,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """
        자동매매 반복 실행의 중단을 요청한다.

        현재 진행 중인 API 호출이나 종목 처리는 강제로
        끊지 않고, 현재 작업이 끝난 뒤 안전하게 중단한다.

        Parameters
        ----------
        wait
            True이면 작업 스레드 종료를 기다린다.

        timeout
            스레드 종료를 기다릴 최대 시간.
            None이면 종료될 때까지 기다린다.
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

        if (
            wait
            and worker_thread is not None
            and worker_thread is not threading.current_thread()
        ):
            worker_thread.join(timeout=timeout)

        with self._state_lock:
            worker_alive = (
                worker_thread is not None
                and worker_thread.is_alive()
            )

            if not worker_alive:
                self._status = TradingStatus.STOPPED
                self._worker_thread = None

        if worker_alive:
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
        체결 동기화와 전체 종목 전략 실행을
        한 번만 수행한다.

        반복 자동매매가 실행 중이면 중복 주문을 방지하기
        위해 별도의 1회 실행을 허용하지 않는다.
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
            cycle_result = self._run_cycle()

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

    def get_status(self) -> str:
        """
        현재 Controller 상태를 문자열로 반환한다.
        """
        with self._state_lock:
            return self._status.value

    def get_state(self) -> dict[str, Any]:
        """
        현재 상태와 최근 실행 정보를 반환한다.
        """
        with self._state_lock:
            worker_alive = (
                self._worker_thread is not None
                and self._worker_thread.is_alive()
            )

            status = self._status.value

        return {
            "status": status,
            "worker_alive": worker_alive,
            "interval_seconds": self.interval_seconds,
            "stock_count": len(self.stock_universe),
            "last_error": self.last_error,
            "last_execution_results": (
                self.last_execution_results
            ),
            "last_results": self.last_results,
        }

    def shutdown(
        self,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """
        프로그램 종료 전에 자동매매 작업을 정리한다.
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
        자동매매 작업 스레드에서 실행되는 반복 루프.
        """
        try:
            while not self._stop_event.is_set():
                acquired = self._run_lock.acquire(
                    blocking=False
                )

                if not acquired:
                    self.last_error = (
                        "다른 매매 작업이 실행 중이어서 "
                        "이번 주기를 건너뛰었습니다."
                    )

                else:
                    try:
                        self._run_cycle()

                    finally:
                        self._run_lock.release()

                if self._stop_event.wait(
                    self.interval_seconds
                ):
                    break

        except Exception as error:
            self.last_error = str(error)

        finally:
            with self._state_lock:
                self._status = TradingStatus.STOPPED
                self._worker_thread = None

            self._stop_event.set()

    def _run_cycle(self) -> dict[str, Any]:
        """
        자동매매 한 주기를 실행한다.

        실행 순서
        ---------
        1. 기존 미완료 주문 체결 동기화
        2. PositionManager 갱신
        3. 전체 종목 전략 및 주문 실행

        PositionManager 갱신은 현재 ExecutionManager 내부의
        position_refresher 설정을 통해 수행된다.
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

        self.last_execution_results = (
            execution_results
        )

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

        return {
            "execution_results": (
                self.last_execution_results
            ),
            "trading_results": self.last_results,
        }

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