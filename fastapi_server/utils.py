import logging


class Inform(logging.Logger):
    trace = 15

    def inform(self, msg, *args, **kwargs):
        self.log(self.trace, msg, *args, **kwargs)


def initialize_api_logger():
    logging.setLoggerClass(Inform)
    logging.addLevelName(15, "INFORM")

    api_logger_name = "api_logger"

    api_logger = logging.getLogger(api_logger_name)
    api_logger.setLevel("INFORM")
    handler = logging.StreamHandler()  # 예제로 콘솔 핸들러 사용
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "[%(endpoint_name)s]: "
        "%(asctime)s | %(levelname)s | %(message)s"
    )
    handler.setFormatter(formatter)
    api_logger.addHandler(handler)
