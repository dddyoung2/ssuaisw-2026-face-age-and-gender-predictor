"""List OpenCV camera indices that can be opened."""

import argparse

import cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe OpenCV camera indices.")
    parser.add_argument("--max-index", type=int, default=6)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    for index in range(args.max_index + 1):
        cap = cv2.VideoCapture(index)
        opened = cap.isOpened()
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if opened else 0
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if opened else 0
        print(f"camera_index={index} opened={opened} size={width}x{height}")
        cap.release()


if __name__ == "__main__":
    main()
