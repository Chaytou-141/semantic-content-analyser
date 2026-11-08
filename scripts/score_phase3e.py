"""Score an exported human CSV using frozen Phase 3D rankings, never inference."""
import argparse
import csv
import json
from pathlib import Path
from phase3e_review import load_reviews, score_reviews

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviews', required=True, type=Path)
    parser.add_argument('--registry', type=Path, default=ROOT/'evaluations/phase3e/packet-registry.json')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        registry = json.loads(args.registry.read_text(encoding='utf-8'))
        result = score_reviews(registry, load_reviews(args.reviews,registry))
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            with args.output.open('x',encoding='utf-8') as file:
                file.write(json.dumps(result,indent=2)+'\n')
            print(json.dumps({'saved':str(args.output),'decisions':result['decision_counts'],'aggregates':result['aggregates']},indent=2))
        else:
            print(json.dumps(result,indent=2))
    except (ValueError,OSError,csv.Error) as error:
        parser.exit(2, str(error)+'\n')


if __name__=='__main__':
    main()
