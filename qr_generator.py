"""
Self-contained QR Code generator that creates pure SVG QR codes.
Uses the `qrcode` library with SVG factory, and provides clean data URI / SVG string output.
No external network or CDN calls required.
"""

import io
from typing import Optional
import qrcode
import qrcode.image.svg

def generate_qr_svg(url: str, box_size: int = 10, size: Optional[int] = None) -> str:
    """Generate a crisp SVG representation of a QR code pointing to `url`."""
    factory = qrcode.image.svg.SvgPathImage
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
        image_factory=factory,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(attrib={'class': 'qr-code-svg', 'style': 'max-width: 100%; height: auto;'})
    stream = io.BytesIO()
    img.save(stream)
    return stream.getvalue().decode('utf-8')
