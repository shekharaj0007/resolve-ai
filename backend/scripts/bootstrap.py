"""Train the models and load the queue."""

from backend.app.ml.train import train
from backend.scripts.seed import seed


def main() -> None:
    train()
    seed()


if __name__ == "__main__":
    main()
