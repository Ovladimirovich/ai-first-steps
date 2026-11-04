import argparse

from .server import serve


def main():
    parser = argparse.ArgumentParser(description="Локальная AI Video Factory")
    parser.add_argument("--host", default="0.0.0.0", help="адрес прослушивания (по умолчанию 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
