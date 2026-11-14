"""q2q serve [--shadow] | q2q pull | q2q train [every] | q2q train2 [every] | q2q board [minutes] | q2q replay [names] [--hours 4]"""
import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="q2q")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="answer live requests")
    serve.add_argument("--shadow", action="store_true", help="compute everything, insert nothing")
    sub.add_parser("pull", help="rebuild the history caches")
    trainer = sub.add_parser("train", help="train the ranker on live feedback")
    trainer.add_argument("every", nargs="?", type=int, default=0)
    trainer2 = sub.add_parser("train2", help="train ranker2 (click and purchase models) on live feedback")
    trainer2.add_argument("every", nargs="?", type=int, default=0)
    board = sub.add_parser("board", help="our models on the leaderboard, read directly")
    board.add_argument("minutes", nargs="?", type=int, default=60)
    replay = sub.add_parser("replay", help="score strategies offline on our logged requests")
    replay.add_argument("names", nargs="*", default=["baseline", "rules2", "rules4", "ranker", "ranker2", "cold1", "cold2"])
    replay.add_argument("--hours", type=float, default=4)
    replay.add_argument("--refresh", action="store_true", help="pull the window again instead of using the cache")
    replay.add_argument("--organic", type=int, default=4000, help="requests with an organic purchase to replay")
    replay.add_argument("--sample", type=int, default=2000, help="uniform sample of requests for overlap")
    args = parser.parse_args()
    if args.cmd == "replay":
        from q2q import replay as offline
        offline.run(args.names, args.hours, args.refresh, args.organic, args.sample)
    elif args.cmd == "serve":
        from q2q import serve as router
        router.run(shadow=args.shadow)
    elif args.cmd == "train":
        from q2q import train
        train.run(args.every)
    elif args.cmd == "train2":
        from q2q import train2
        train2.run(args.every)
    elif args.cmd == "board":
        from q2q import evaluate
        evaluate.models_report(args.minutes)
    else:
        from q2q import data
        data.pull()


if __name__ == "__main__":
    main()
