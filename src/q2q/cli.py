"""q2q serve [--shadow] | q2q pull"""
import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="q2q")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="answer live requests")
    serve.add_argument("--shadow", action="store_true", help="compute everything, insert nothing")
    sub.add_parser("pull", help="rebuild the history caches")
    args = parser.parse_args()
    if args.cmd == "serve":
        from q2q import serve as router
        router.run(shadow=args.shadow)
    else:
        from q2q import data
        data.pull()


if __name__ == "__main__":
    main()
