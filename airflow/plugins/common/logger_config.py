import logging


class Inform(logging.Logger):
    trace = 15

    def inform(self, msg, *args, **kwargs):
        self.log(self.trace, msg, *args, **kwargs)


def setup_logger(name: str = "api_logger") -> logging.Logger:
    logging.setLoggerClass(Inform)
    logging.addLevelName(15, "INFORM")

    api_logger = logging.getLogger(name)
    if not api_logger.hasHandlers():
        api_logger.setLevel("INFORM")
        handler = logging.StreamHandler()  # 예제로 콘솔 핸들러 사용
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        handler.setFormatter(formatter)
        api_logger.addHandler(handler)

    return api_logger
