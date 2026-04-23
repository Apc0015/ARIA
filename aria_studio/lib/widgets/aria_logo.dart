import 'package:flutter/material.dart';

/// ARIA brand logo widget — uses the real logo image asset.
///
/// [size] variants:
///   'full'    — large logo image (login screen, splash)
///   'compact' — medium logo (app header)
///   'icon'    — small square icon (sidebar, favicon)
class AriaLogo extends StatelessWidget {
  const AriaLogo({
    super.key,
    this.size = 'full',
    this.dark = false,
  });

  final String size;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    switch (size) {
      case 'icon':
        return _logoImage(height: 48);
      case 'compact':
        return _logoImage(height: 40);
      case 'full':
      default:
        return _logoImage(height: 120);
    }
  }

  Widget _logoImage({required double height}) {
    return Image.asset(
      'assets/images/aria_logo.png',
      height: height,
      fit: BoxFit.contain,
      color: dark ? Colors.white.withOpacity(0.92) : null,
      colorBlendMode: dark ? BlendMode.modulate : null,
    );
  }
}
