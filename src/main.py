"""Print the validated configuration for stage 1."""

from cli import parse_config


def main() -> None:
    """Print the five settings as key-value pairs."""
    for key, value in vars(parse_config()).items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
