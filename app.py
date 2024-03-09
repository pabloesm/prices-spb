from src import main
from src.config.environment_vars import EnvironmentVars
from src.config.logger import setup_logger

logger = setup_logger(EnvironmentVars().get_logging_level())

if __name__ == "__main__":
    main.main()
