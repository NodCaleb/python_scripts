import sys

try:
    import qrcode
except ModuleNotFoundError:
    print("Missing dependency: qrcode")
    print("Install it with: python -m pip install qrcode[pil]")
    raise SystemExit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: python qr.py \"text to encode\" [output.png]")
        return

    data = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "qrcode.png"

    qr = qrcode.make(data)
    qr.save(output)

    print(f"QR code saved to {output}")

if __name__ == "__main__":
    main()