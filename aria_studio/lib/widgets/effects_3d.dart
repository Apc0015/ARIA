// ARIA Studio — 3D motion effects
// Deep Space Research Terminal aesthetic
// All 3D via Matrix4 perspective transforms + mouse tracking
// AnimationControllers: listeners added ONCE in initState, disposed in dispose()

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

import '../theme/aria_theme.dart';

// ═════════════════════════════════════════════════════════════════
// Aria3dCard — mouse-tracked tilt with spring physics
// ═════════════════════════════════════════════════════════════════

class Aria3dCard extends StatefulWidget {
  const Aria3dCard({
    super.key,
    required this.child,
    this.maxTiltDeg = 8.0,
    this.scaleFactor = 1.02,
    this.glowColor,
  });

  final Widget child;
  final double maxTiltDeg;
  final double scaleFactor;
  final Color? glowColor;

  @override
  State<Aria3dCard> createState() => _Aria3dCardState();
}

class _Aria3dCardState extends State<Aria3dCard>
    with SingleTickerProviderStateMixin {
  double _rotX = 0.0;
  double _rotY = 0.0;
  bool _hovered = false;

  late final AnimationController _springCtrl;
  late Animation<double> _rotXAnim;
  late Animation<double> _rotYAnim;

  @override
  void initState() {
    super.initState();
    _springCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    );
    _rotXAnim = Tween<double>(begin: 0, end: 0).animate(
        CurvedAnimation(parent: _springCtrl, curve: Curves.easeOut));
    _rotYAnim = Tween<double>(begin: 0, end: 0).animate(
        CurvedAnimation(parent: _springCtrl, curve: Curves.easeOut));
    // Single listener registered once — no leak
    _springCtrl.addListener(_onAnimTick);
  }

  void _onAnimTick() {
    if (mounted) {
      setState(() {
        _rotX = _rotXAnim.value;
        _rotY = _rotYAnim.value;
      });
    }
  }

  @override
  void dispose() {
    _springCtrl.removeListener(_onAnimTick);
    _springCtrl.dispose();
    super.dispose();
  }

  void _onHover(PointerEvent event, BoxConstraints box) {
    final cx = box.maxWidth / 2;
    final cy = box.maxHeight / 2;
    final dx = (event.localPosition.dx - cx) / cx;
    final dy = (event.localPosition.dy - cy) / cy;

    final maxRad = widget.maxTiltDeg * math.pi / 180.0;
    final targetX = -dy * maxRad;
    final targetY = dx * maxRad;

    _springCtrl.stop();
    _springCtrl.duration = const Duration(milliseconds: 400);
    _rotXAnim = Tween<double>(begin: _rotX, end: targetX).animate(
        CurvedAnimation(parent: _springCtrl, curve: Curves.easeOut));
    _rotYAnim = Tween<double>(begin: _rotY, end: targetY).animate(
        CurvedAnimation(parent: _springCtrl, curve: Curves.easeOut));
    _springCtrl.forward(from: 0);
  }

  void _onExit() {
    _springCtrl.stop();
    _springCtrl.duration = const Duration(milliseconds: 600);
    _rotXAnim = Tween<double>(begin: _rotX, end: 0).animate(
        CurvedAnimation(parent: _springCtrl, curve: Curves.elasticOut));
    _rotYAnim = Tween<double>(begin: _rotY, end: 0).animate(
        CurvedAnimation(parent: _springCtrl, curve: Curves.elasticOut));
    _springCtrl.forward(from: 0);
    setState(() => _hovered = false);
  }

  Matrix4 get _matrix {
    // Use a very gentle perspective (0.0003) so content NEVER goes behind
    // the camera plane — eliminates the "disappearing on hover" bug.
    // Tilt is capped at maxTiltDeg in _onHover, keeping it subtle.
    final m = Matrix4.identity()
      ..setEntry(3, 2, 0.0003) // very shallow perspective — safe
      ..rotateX(_rotX)
      ..rotateY(_rotY);
    return m;
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (ctx, box) {
      return MouseRegion(
        cursor: SystemMouseCursors.basic,
        onEnter: (_) => setState(() {
          _hovered = true;
          _springCtrl.duration = const Duration(milliseconds: 400);
        }),
        onExit: (_) => _onExit(),
        onHover: (e) => _onHover(e, box),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(8),
            boxShadow: _hovered
                ? [
                    BoxShadow(
                      color: (widget.glowColor ?? AriaTheme.brandIndigo)
                          .withAlpha(45),
                      blurRadius: 32,
                      spreadRadius: 1,
                      offset: Offset(_rotY * 12, -_rotX * 12),
                    ),
                  ]
                : [
                    BoxShadow(
                      color: Colors.black.withAlpha(50),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ],
          ),
          // clipBehavior.none prevents the perspective transform from clipping
          // child content at the card edges during tilt.
          child: Transform(
            transform: _matrix,
            alignment: Alignment.center,
            filterQuality: FilterQuality.low,
            // Disable hit-test transform so pointer events use pre-tilt coords.
            // This fixes Switch/GestureDetector children not receiving taps
            // when the card is tilted (3D perspective distorts hit zones).
            transformHitTests: false,
            child: widget.child,
          ),
        ),
      );
    });
  }
}

// ═════════════════════════════════════════════════════════════════
// Aria3dOrb — enhanced rotating orb with 5 rings + particle dust
// ═════════════════════════════════════════════════════════════════

class Aria3dOrb extends StatefulWidget {
  const Aria3dOrb({
    super.key,
    this.size = 160.0,
    this.color = AriaTheme.brandIndigo,
  });
  final double size;
  final Color color;

  @override
  State<Aria3dOrb> createState() => _Aria3dOrbState();
}

class _Aria3dOrbState extends State<Aria3dOrb> with TickerProviderStateMixin {
  late final AnimationController _rotCtrl;
  late final AnimationController _floatCtrl;
  late final AnimationController _pulseCtrl;
  late final AnimationController _dustCtrl;
  late final Animation<double> _floatAnim;
  late final Animation<double> _pulseAnim;

  double _mouseX = 0.0;
  double _mouseY = 0.0;

  // Dust particles: [angle, radius, size, speed]
  late final List<List<double>> _dustParticles;

  @override
  void initState() {
    super.initState();

    _rotCtrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 12),
    )..repeat();

    _floatCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 3500),
    )..repeat(reverse: true);

    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    )..repeat(reverse: true);

    _dustCtrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 20),
    )..repeat();

    _floatAnim = Tween<double>(begin: -10.0, end: 10.0).animate(
        CurvedAnimation(parent: _floatCtrl, curve: Curves.easeInOut));

    _pulseAnim = Tween<double>(begin: 0.95, end: 1.05).animate(
        CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut));

    // Generate dust cloud particles
    final rng = math.Random(42);
    _dustParticles = List.generate(20, (_) {
      final angle = rng.nextDouble() * 2 * math.pi;
      final radius = 0.38 + rng.nextDouble() * 0.18; // 38–56% of orb size
      final sz = 1.0 + rng.nextDouble() * 2.0;
      final speed = 0.4 + rng.nextDouble() * 0.8;
      return [angle, radius, sz, speed];
    });
  }

  @override
  void dispose() {
    _rotCtrl.dispose();
    _floatCtrl.dispose();
    _pulseCtrl.dispose();
    _dustCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.size;
    final c = widget.color;

    return MouseRegion(
      cursor: SystemMouseCursors.basic,
      onHover: (e) => setState(() {
        _mouseX = (e.localPosition.dx - s / 2) / (s / 2);
        _mouseY = (e.localPosition.dy - s / 2) / (s / 2);
      }),
      onExit: (_) => setState(() {
        _mouseX = 0;
        _mouseY = 0;
      }),
      child: AnimatedBuilder(
        animation:
            Listenable.merge([_rotCtrl, _floatCtrl, _pulseCtrl, _dustCtrl]),
        builder: (_, __) {
          final rotY = _rotCtrl.value * 2 * math.pi + _mouseX * 0.4;
          final rotX = -_mouseY * 0.3;

          final m = Matrix4.identity()
            ..setEntry(3, 2, 0.0006)
            ..rotateX(rotX)
            ..rotateY(rotY);

          return Transform.translate(
            offset: Offset(0, _floatAnim.value),
            child: Transform(
              transform: m,
              alignment: Alignment.center,
              child: SizedBox(
                width: s,
                height: s,
                child: Stack(alignment: Alignment.center, children: [
                  // Ring 1: outermost ambient
                  _Ring(
                    size: s,
                    color: c,
                    alpha: 10,
                    strokeWidth: 0.8,
                    rotateZ: _rotCtrl.value * -math.pi * 0.5,
                  ),
                  // Ring 2: outer
                  _Ring(
                    size: s * 0.88,
                    color: c,
                    alpha: 18,
                    strokeWidth: 1.0,
                    rotateZ: _rotCtrl.value * -math.pi,
                  ),
                  // Ring 3: mid tilted 60°
                  Transform(
                    transform: Matrix4.identity()
                      ..setEntry(3, 2, 0.0006)
                      ..rotateX(math.pi / 3),
                    alignment: Alignment.center,
                    child: _Ring(
                      size: s * 0.82,
                      color: c,
                      alpha: 30,
                      strokeWidth: 1.0,
                      rotateZ: _rotCtrl.value * math.pi * 1.3,
                    ),
                  ),
                  // Ring 4: inner tilted 30°
                  Transform(
                    transform: Matrix4.identity()
                      ..setEntry(3, 2, 0.0006)
                      ..rotateX(math.pi / 6),
                    alignment: Alignment.center,
                    child: _Ring(
                      size: s * 0.60,
                      color: c,
                      alpha: 50,
                      strokeWidth: 1.0,
                      rotateZ: _rotCtrl.value * -math.pi * 0.8,
                    ),
                  ),
                  // Ring 5: equatorial tilted 80°
                  Transform(
                    transform: Matrix4.identity()
                      ..setEntry(3, 2, 0.0006)
                      ..rotateX(math.pi * 0.44),
                    alignment: Alignment.center,
                    child: _Ring(
                      size: s * 0.44,
                      color: AriaTheme.accentViolet,
                      alpha: 40,
                      strokeWidth: 0.8,
                      rotateZ: _rotCtrl.value * math.pi * 1.7,
                    ),
                  ),
                  // Dust cloud
                  CustomPaint(
                    size: Size(s, s),
                    painter: _DustCloudPainter(
                      particles: _dustParticles,
                      animValue: _dustCtrl.value,
                      color: c,
                      orbSize: s,
                    ),
                  ),
                  // Core sphere — multi-layer radial gradient
                  Transform.scale(
                    scale: _pulseAnim.value,
                    child: Stack(alignment: Alignment.center, children: [
                      // Outer glow halo
                      Container(
                        width: s * 0.46,
                        height: s * 0.46,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          boxShadow: [
                            BoxShadow(
                                color: c.withAlpha(80),
                                blurRadius: 40,
                                spreadRadius: 8),
                            BoxShadow(
                                color: AriaTheme.accentViolet.withAlpha(40),
                                blurRadius: 60,
                                spreadRadius: 12),
                          ],
                        ),
                      ),
                      // Core gradient sphere
                      Container(
                        width: s * 0.38,
                        height: s * 0.38,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: RadialGradient(
                            center: const Alignment(-0.3, -0.35),
                            radius: 0.9,
                            colors: [
                              Colors.white.withAlpha(60),
                              c.withAlpha(220),
                              c.withAlpha(140),
                              AriaTheme.accentViolet.withAlpha(100),
                              AriaTheme.accentViolet.withAlpha(20),
                            ],
                            stops: const [0.0, 0.2, 0.5, 0.75, 1.0],
                          ),
                          boxShadow: [
                            BoxShadow(
                                color: c.withAlpha(120),
                                blurRadius: 30,
                                spreadRadius: 4),
                            BoxShadow(
                                color: c.withAlpha(60),
                                blurRadius: 60,
                                spreadRadius: 10),
                          ],
                        ),
                        child: Center(
                          child: Icon(Icons.manage_search,
                              size: s * 0.14,
                              color: Colors.white.withAlpha(220)),
                        ),
                      ),
                      // Light reflection highlight (top-left arc)
                      Positioned(
                        top: s * 0.038,
                        left: s * 0.09,
                        child: Container(
                          width: s * 0.12,
                          height: s * 0.06,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(s * 0.04),
                            gradient: LinearGradient(
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                              colors: [
                                Colors.white.withAlpha(90),
                                Colors.white.withAlpha(0),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ]),
                  ),
                  // Orbiting dots
                  _OrbitingDot(
                    orbitRadius: s * 0.42,
                    angle: _rotCtrl.value * 2 * math.pi,
                    color: c,
                  ),
                  _OrbitingDot(
                    orbitRadius: s * 0.38,
                    angle: _rotCtrl.value * 2 * math.pi + math.pi,
                    color: AriaTheme.accentViolet,
                  ),
                  _OrbitingDot(
                    orbitRadius: s * 0.48,
                    angle: _rotCtrl.value * 2 * math.pi + math.pi / 2,
                    color: Colors.white.withAlpha(120),
                    dotSize: 3.0,
                  ),
                ]),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _Ring extends StatelessWidget {
  const _Ring({
    required this.size,
    required this.color,
    required this.alpha,
    required this.strokeWidth,
    this.rotateZ = 0.0,
  });
  final double size, strokeWidth, rotateZ;
  final Color color;
  final int alpha;

  @override
  Widget build(BuildContext context) {
    return Transform.rotate(
      angle: rotateZ,
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: color.withAlpha(alpha), width: strokeWidth),
        ),
      ),
    );
  }
}

class _OrbitingDot extends StatelessWidget {
  const _OrbitingDot({
    required this.orbitRadius,
    required this.angle,
    required this.color,
    this.dotSize = 5.0,
  });
  final double orbitRadius, angle, dotSize;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final x = math.cos(angle) * orbitRadius;
    final y = math.sin(angle) * orbitRadius * 0.35; // flatten for 3D illusion
    return Transform.translate(
      offset: Offset(x, y),
      child: Container(
        width: dotSize,
        height: dotSize,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: color,
          boxShadow: [BoxShadow(color: color.withAlpha(180), blurRadius: 8)],
        ),
      ),
    );
  }
}

class _DustCloudPainter extends CustomPainter {
  const _DustCloudPainter({
    required this.particles,
    required this.animValue,
    required this.color,
    required this.orbSize,
  });

  final List<List<double>> particles;
  final double animValue;
  final Color color;
  final double orbSize;

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;

    for (final p in particles) {
      final baseAngle = p[0];
      final radiusFraction = p[1];
      final dotSize = p[2];
      final speed = p[3];

      final angle = baseAngle + animValue * 2 * math.pi * speed;
      final r = radiusFraction * orbSize / 2;
      final x = cx + math.cos(angle) * r;
      final y = cy + math.sin(angle) * r * 0.4; // perspective flatten

      final normR = radiusFraction - 0.38;
      final opacity = (1.0 - (normR / 0.18).abs()).clamp(0.1, 0.6);

      final paint = Paint()
        ..color = color.withAlpha((opacity * 100).round())
        ..style = PaintingStyle.fill;

      canvas.drawCircle(Offset(x, y), dotSize / 2, paint);
    }
  }

  @override
  bool shouldRepaint(_DustCloudPainter old) =>
      old.animValue != animValue || old.color != color;
}

// ═════════════════════════════════════════════════════════════════
// Aria3dButton — press depth shift
// ═════════════════════════════════════════════════════════════════

class Aria3dButton extends StatefulWidget {
  const Aria3dButton({
    super.key,
    required this.label,
    required this.onTap,
    this.icon,
    this.loading = false,
    this.enabled = true,
  });
  final String label;
  final VoidCallback onTap;
  final IconData? icon;
  final bool loading;
  final bool enabled;

  @override
  State<Aria3dButton> createState() => _Aria3dButtonState();
}

class _Aria3dButtonState extends State<Aria3dButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _pressAnim;
  bool _hover = false;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 100));
    _pressAnim = Tween<double>(begin: 0, end: 1).animate(_ctrl);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Matrix4 get _matrix {
    final press = _pressAnim.value;
    // Simple scale-down press — no perspective transform to avoid
    // compounding with parent Aria3dCard's perspective matrix.
    return Matrix4.identity()
      ..scale(1.0 - press * 0.03, 1.0 - press * 0.03, 1.0);
  }

  @override
  Widget build(BuildContext context) {
    final active = widget.enabled && !widget.loading;

    return MouseRegion(
      cursor: active ? SystemMouseCursors.click : SystemMouseCursors.basic,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTapDown: active ? (_) => _ctrl.forward() : null,
        onTapUp: active
            ? (_) {
                _ctrl.reverse();
                widget.onTap();
              }
            : null,
        onTapCancel: () => _ctrl.reverse(),
        child: AnimatedBuilder(
          animation: _pressAnim,
          builder: (_, child) => Transform(
            transform: _matrix,
            alignment: Alignment.center,
            child: child,
          ),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 11),
            decoration: BoxDecoration(
              color: active
                  ? (_hover
                      ? AriaTheme.brandIndigo.withAlpha(220)
                      : AriaTheme.brandIndigo)
                  : AriaTheme.bg3,
              borderRadius: BorderRadius.circular(6),
              boxShadow: active
                  ? [
                      BoxShadow(
                        color: AriaTheme.brandIndigo
                            .withAlpha(_hover ? 100 : 60),
                        blurRadius: _hover ? 20 : 10,
                        offset: Offset(0, _hover ? 8 : 4),
                        spreadRadius: _hover ? 2 : 0,
                      ),
                    ]
                  : null,
            ),
            child: widget.loading
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                        strokeWidth: 1.5, color: Colors.white))
                : Row(mainAxisSize: MainAxisSize.min, children: [
                    if (widget.icon != null) ...[
                      Icon(widget.icon,
                          size: 14,
                          color:
                              active ? Colors.white : AriaTheme.textSubtle),
                      const SizedBox(width: 6),
                    ],
                    Text(widget.label,
                        style: AriaTheme.inter(
                            size: 13,
                            weight: FontWeight.w500,
                            color:
                                active ? Colors.white : AriaTheme.textSubtle)),
                    const SizedBox(width: 6),
                    Icon(Icons.arrow_forward,
                        size: 13,
                        color: active ? Colors.white : AriaTheme.textSubtle),
                  ]),
          ),
        ),
      ),
    );
  }
}

// ═════════════════════════════════════════════════════════════════
// Aria3dMetricTile — Y-axis flip on value change
// ═════════════════════════════════════════════════════════════════

class Aria3dMetricTile extends StatefulWidget {
  const Aria3dMetricTile({
    super.key,
    required this.label,
    required this.value,
    required this.icon,
    this.accent = AriaTheme.textMuted,
  });
  final String label, value;
  final IconData icon;
  final Color accent;

  @override
  State<Aria3dMetricTile> createState() => _Aria3dMetricTileState();
}

class _Aria3dMetricTileState extends State<Aria3dMetricTile>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _flip;
  String _displayValue = '';

  @override
  void initState() {
    super.initState();
    _displayValue = widget.value;
    _ctrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 400));
    _flip = Tween<double>(begin: 0, end: math.pi)
        .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut));
  }

  @override
  void didUpdateWidget(Aria3dMetricTile old) {
    super.didUpdateWidget(old);
    if (old.value != widget.value) {
      _ctrl.forward(from: 0).then((_) {
        if (mounted) setState(() => _displayValue = widget.value);
        _ctrl.reverse();
      });
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _flip,
      builder: (_, child) {
        final angle = _flip.value;
        final m = Matrix4.identity()
          ..setEntry(3, 2, 0.002)
          ..rotateY(angle);
        return Transform(
          transform: m,
          alignment: Alignment.center,
          child: child,
        );
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: AriaTheme.bg2,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: AriaTheme.borderStandard),
        ),
        child: Row(children: [
          Icon(widget.icon, size: 16, color: widget.accent),
          const SizedBox(width: 10),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(_displayValue,
                style: AriaTheme.mono(
                    size: 20,
                    weight: FontWeight.w500,
                    color: widget.accent,
                    height: 1.0)),
            Text(widget.label,
                style: AriaTheme.inter(size: 10, color: AriaTheme.textSubtle, letterSpacing: 0.6)),
          ]),
        ]),
      ),
    );
  }
}

// ═════════════════════════════════════════════════════════════════
// Aria3dGrid — perspective scrolling background grid
// ═════════════════════════════════════════════════════════════════

class Aria3dGrid extends StatefulWidget {
  const Aria3dGrid({super.key});

  @override
  State<Aria3dGrid> createState() => _Aria3dGridState();
}

class _Aria3dGridState extends State<Aria3dGrid>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 8))
      ..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) => CustomPaint(
        painter: _GridPainter(scroll: _ctrl.value),
        child: const SizedBox.expand(),
      ),
    );
  }
}

class _GridPainter extends CustomPainter {
  _GridPainter({required this.scroll});
  final double scroll;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AriaTheme.brandIndigo.withAlpha(12)
      ..strokeWidth = 0.5
      ..style = PaintingStyle.stroke;

    const cols = 12;
    const rows = 16;
    final vp = size.height * 0.6; // vanishing point Y
    final centerX = size.width / 2;

    // Horizontal lines — perspective converge
    for (int r = 0; r <= rows; r++) {
      final t = ((r / rows) + scroll) % 1.0;
      final y = vp + (size.height - vp) * t * t;
      if (y > vp) {
        canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
      }
    }

    // Vertical lines — converge to center vanishing point
    for (int c = 0; c <= cols; c++) {
      final xBottom = (c / cols) * size.width;
      canvas.drawLine(
        Offset(xBottom, size.height),
        Offset(centerX, vp),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_GridPainter old) => old.scroll != scroll;
}

// ═════════════════════════════════════════════════════════════════
// Aria3dPageRoute — 3D unfold page transition
// ═════════════════════════════════════════════════════════════════

class Aria3dPageRoute<T> extends PageRouteBuilder<T> {
  Aria3dPageRoute({required Widget page, super.settings})
      : super(
          pageBuilder: (_, __, ___) => page,
          transitionDuration: const Duration(milliseconds: 480),
          reverseTransitionDuration: const Duration(milliseconds: 380),
          transitionsBuilder: (ctx, anim, secondaryAnim, child) {
            final curved =
                CurvedAnimation(parent: anim, curve: Curves.easeOutCubic);
            return AnimatedBuilder(
              animation: curved,
              child: child,
              builder: (_, c) {
                final t = curved.value;
                final m = Matrix4.identity()
                  ..setEntry(3, 2, 0.001)
                  ..rotateY((1 - t) * math.pi / 2);
                return Transform(
                  transform: m,
                  alignment: Alignment.centerRight,
                  child: Opacity(opacity: t.clamp(0.0, 1.0), child: c),
                );
              },
            );
          },
        );
}

// ═════════════════════════════════════════════════════════════════
// Aria3dStarField — full-screen animated starfield with parallax
// ═════════════════════════════════════════════════════════════════

/// Star data: position, size, speed, depth layer, twinkle phase
class _Star {
  _Star({
    required this.x,
    required this.y,
    required this.size,
    required this.speed,
    required this.layer,
    required this.phase,
  });
  double x, y;
  final double size, speed, phase;
  final int layer; // 0=far, 1=mid, 2=near
}

class Aria3dStarField extends StatefulWidget {
  const Aria3dStarField({
    super.key,
    this.starCount = 150,
    this.child,
  });

  final int starCount;
  final Widget? child;

  @override
  State<Aria3dStarField> createState() => _Aria3dStarFieldState();
}

class _Aria3dStarFieldState extends State<Aria3dStarField>
    with SingleTickerProviderStateMixin {
  late final AnimationController _driftCtrl;
  late final List<_Star> _stars;

  double _mouseX = 0.0;
  double _mouseY = 0.0;

  @override
  void initState() {
    super.initState();

    _driftCtrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 30),
    )..repeat();

    final rng = math.Random(7331);
    _stars = List.generate(widget.starCount, (i) {
      // Distribute across 3 layers: 50% far, 30% mid, 20% near
      final layer = i < widget.starCount * 0.5
          ? 0
          : i < widget.starCount * 0.8
              ? 1
              : 2;

      final double size;
      final double speed;
      if (layer == 0) {
        size = 0.5 + rng.nextDouble() * 0.8; // 0.5–1.3
        speed = 0.02 + rng.nextDouble() * 0.03;
      } else if (layer == 1) {
        size = 1.0 + rng.nextDouble() * 0.8; // 1.0–1.8
        speed = 0.05 + rng.nextDouble() * 0.05;
      } else {
        size = 1.6 + rng.nextDouble() * 0.9; // 1.6–2.5
        speed = 0.10 + rng.nextDouble() * 0.08;
      }

      return _Star(
        x: rng.nextDouble(),
        y: rng.nextDouble(),
        size: size,
        speed: speed,
        layer: layer,
        phase: rng.nextDouble() * 2 * math.pi,
      );
    });
  }

  @override
  void dispose() {
    _driftCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.basic,
      onHover: (e) {
        final box = context.findRenderObject() as RenderBox?;
        if (box != null) {
          final size = box.size;
          setState(() {
            _mouseX = (e.localPosition.dx / size.width) * 2 - 1;
            _mouseY = (e.localPosition.dy / size.height) * 2 - 1;
          });
        }
      },
      onExit: (_) => setState(() {
        _mouseX = 0;
        _mouseY = 0;
      }),
      child: AnimatedBuilder(
        animation: _driftCtrl,
        builder: (_, child) {
          return CustomPaint(
            painter: _StarFieldPainter(
              stars: _stars,
              animValue: _driftCtrl.value,
              mouseX: _mouseX,
              mouseY: _mouseY,
            ),
            child: child ?? const SizedBox.expand(),
          );
        },
        child: widget.child,
      ),
    );
  }
}

class _StarFieldPainter extends CustomPainter {
  const _StarFieldPainter({
    required this.stars,
    required this.animValue,
    required this.mouseX,
    required this.mouseY,
  });

  final List<_Star> stars;
  final double animValue;
  final double mouseX;
  final double mouseY;

  @override
  void paint(Canvas canvas, Size size) {
    // Fill background first
    canvas.drawRect(
      Rect.fromLTWH(0, 0, size.width, size.height),
      Paint()..color = AriaTheme.bg0,
    );

    // Layer parallax offsets: far=subtle, near=pronounced
    final layerParallax = [
      Offset(mouseX * 4, mouseY * 4),
      Offset(mouseX * 10, mouseY * 10),
      Offset(mouseX * 20, mouseY * 20),
    ];

    // Base opacity and twinkle amplitude per layer
    const layerBaseOpacity = [0.20, 0.40, 0.65];
    const layerOpacityRange = [0.15, 0.20, 0.15];

    for (final star in stars) {
      // Drift: stars slowly move downward, wrapping
      final driftedY = (star.y + animValue * star.speed) % 1.0;

      final parallax = layerParallax[star.layer];
      final px = star.x * size.width + parallax.dx;
      final py = driftedY * size.height + parallax.dy;

      // Twinkle oscillation — 3 cycles over the 30s loop
      final twinkle =
          math.sin(animValue * 2 * math.pi * 3 + star.phase);
      final baseOp = layerBaseOpacity[star.layer];
      final range = layerOpacityRange[star.layer];
      final opacity = (baseOp + twinkle * range).clamp(0.0, 1.0);

      final paint = Paint()
        ..color = Colors.white.withAlpha((opacity * 255).round())
        ..style = PaintingStyle.fill;

      // Near stars get a soft glow
      if (star.layer == 2) {
        final glowPaint = Paint()
          ..color = Colors.white.withAlpha((opacity * 40).round())
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2.5);
        canvas.drawCircle(Offset(px, py), star.size * 1.8, glowPaint);
      }

      canvas.drawCircle(Offset(px, py), star.size, paint);
    }
  }

  @override
  bool shouldRepaint(_StarFieldPainter old) =>
      old.animValue != animValue ||
      old.mouseX != mouseX ||
      old.mouseY != mouseY;
}

// ═════════════════════════════════════════════════════════════════
// Aria3dGlassPanel — glassmorphism panel with neon glow border
// ═════════════════════════════════════════════════════════════════

class Aria3dGlassPanel extends StatelessWidget {
  const Aria3dGlassPanel({
    super.key,
    required this.child,
    this.borderRadius = 12.0,
    this.glowColor = AriaTheme.brandIndigo,
    this.glowIntensity = 0.3,
    this.padding = const EdgeInsets.all(20),
  });

  final Widget child;
  final double borderRadius;
  final Color glowColor;
  final double glowIntensity;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    final radius = BorderRadius.circular(borderRadius);
    final glowAlpha = (glowIntensity * 60).round();

    return ClipRRect(
      borderRadius: radius,
      child: Container(
        decoration: BoxDecoration(
          borderRadius: radius,
          color: const Color(0x0AFFFFFF), // rgba(255,255,255,4%)
          border: Border.all(
            color: const Color(0x18FFFFFF), // rgba(255,255,255,~9.4%)
            width: 1.0,
          ),
          boxShadow: [
            // Outer neon glow
            BoxShadow(
              color: glowColor.withAlpha(glowAlpha),
              blurRadius: 40,
              spreadRadius: -5,
            ),
            // Depth shadow
            BoxShadow(
              color: Colors.black.withAlpha(60),
              blurRadius: 20,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Stack(
          children: [
            // Top-edge highlight (simulates inset glow / beveled glass)
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: Container(
                height: 1,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      Colors.white.withAlpha(0),
                      Colors.white.withAlpha(38), // rgba(255,255,255,0.15)
                      Colors.white.withAlpha(0),
                    ],
                  ),
                ),
              ),
            ),
            // Inner surface diagonal shimmer
            Positioned.fill(
              child: Container(
                decoration: BoxDecoration(
                  borderRadius: radius,
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      Colors.white.withAlpha(8), // rgba(255,255,255,0.03)
                      Colors.transparent,
                      Colors.white.withAlpha(4),
                    ],
                    stops: const [0.0, 0.5, 1.0],
                  ),
                ),
              ),
            ),
            Padding(padding: padding, child: child),
          ],
        ),
      ),
    );
  }
}

// ═════════════════════════════════════════════════════════════════
// Aria3dStagger — staggered entrance animation
// ═════════════════════════════════════════════════════════════════

class Aria3dStagger extends StatefulWidget {
  const Aria3dStagger({
    super.key,
    required this.child,
    this.index = 0,
    this.delay = Duration.zero,
    this.baseDelayMs = 0,
    this.axis = Axis.vertical,
  });

  final Widget child;
  final int index;
  final Duration delay;
  final int baseDelayMs;
  final Axis axis;

  @override
  State<Aria3dStagger> createState() => _Aria3dStaggerState();
}

class _Aria3dStaggerState extends State<Aria3dStagger>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _opacity;
  late final Animation<double> _slide;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    );

    _opacity = Tween<double>(begin: 0.0, end: 1.0).animate(
        CurvedAnimation(parent: _ctrl, curve: Curves.easeOutCubic));

    _slide = Tween<double>(begin: 20.0, end: 0.0).animate(
        CurvedAnimation(parent: _ctrl, curve: Curves.easeOutCubic));

    // Use SchedulerBinding so the timer fires inside Flutter's scheduler,
    // not the browser's deferred timer queue (which blocks until user gesture).
    final totalDelay = widget.delay +
        Duration(milliseconds: widget.baseDelayMs + widget.index * 80);
    SchedulerBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (totalDelay == Duration.zero) {
        _ctrl.forward();
      } else {
        Future.delayed(totalDelay, () {
          if (mounted) _ctrl.forward();
        });
      }
    });
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, child) {
        final slideOffset = widget.axis == Axis.vertical
            ? Offset(0, _slide.value)
            : Offset(_slide.value, 0);
        return Opacity(
          opacity: _opacity.value,
          child: Transform.translate(
            offset: slideOffset,
            child: child,
          ),
        );
      },
      child: widget.child,
    );
  }
}

// ═════════════════════════════════════════════════════════════════
// Aria3dFloatingOrb — ambient decorative orb with sine float
// ═════════════════════════════════════════════════════════════════

class Aria3dFloatingOrb extends StatefulWidget {
  const Aria3dFloatingOrb({
    super.key,
    this.size = 40.0,
    required this.color,
    this.opacity = 0.5,
    this.driftAmplitude = 20.0,
    this.driftDuration = const Duration(seconds: 4),
    this.top,
    this.left,
    this.right,
    this.bottom,
  });

  final double size;
  final Color color;
  final double opacity;
  final double driftAmplitude;
  final Duration driftDuration;
  final double? top;
  final double? left;
  final double? right;
  final double? bottom;

  @override
  State<Aria3dFloatingOrb> createState() => _Aria3dFloatingOrbState();
}

class _Aria3dFloatingOrbState extends State<Aria3dFloatingOrb>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _floatAnim;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: widget.driftDuration,
    )..repeat(reverse: true);

    _floatAnim = Tween<double>(
      begin: -widget.driftAmplitude / 2,
      end: widget.driftAmplitude / 2,
    ).animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut));
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final alpha = (widget.opacity * 255).round().clamp(0, 255);
    final glowAlpha = (widget.opacity * 80).round().clamp(0, 255);
    return Positioned(
      top: widget.top,
      left: widget.left,
      right: widget.right,
      bottom: widget.bottom,
      child: IgnorePointer(
        child: AnimatedBuilder(
          animation: _floatAnim,
          builder: (_, __) {
            return Transform.translate(
              offset: Offset(0, _floatAnim.value),
              child: Container(
                width: widget.size,
                height: widget.size,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      widget.color.withAlpha(alpha),
                      widget.color.withAlpha(alpha ~/ 2),
                      widget.color.withAlpha(0),
                    ],
                    stops: const [0.0, 0.4, 1.0],
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: widget.color.withAlpha(glowAlpha),
                      blurRadius: widget.size * 0.6,
                      spreadRadius: widget.size * 0.05,
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

// ═════════════════════════════════════════════════════════════════
// Aria3dScanline — holographic scanline overlay
// ═════════════════════════════════════════════════════════════════

class Aria3dScanline extends StatefulWidget {
  const Aria3dScanline({
    super.key,
    required this.child,
    this.lineSpacing = 3.0,
    this.lineOpacity = 0.015,
    this.sweepDuration = const Duration(seconds: 4),
    this.showSweep = true,
  });

  final Widget child;
  final double lineSpacing;
  final double lineOpacity;
  final Duration sweepDuration;
  final bool showSweep;

  @override
  State<Aria3dScanline> createState() => _Aria3dScanlineState();
}

class _Aria3dScanlineState extends State<Aria3dScanline>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: widget.sweepDuration,
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        widget.child,
        IgnorePointer(
          child: AnimatedBuilder(
            animation: _ctrl,
            builder: (_, __) => CustomPaint(
              painter: _ScanlinePainter(
                scroll: _ctrl.value,
                lineSpacing: widget.lineSpacing,
                lineOpacity: widget.lineOpacity,
                showSweep: widget.showSweep,
                sweepProgress: _ctrl.value,
              ),
              child: const SizedBox.expand(),
            ),
          ),
        ),
      ],
    );
  }
}

class _ScanlinePainter extends CustomPainter {
  const _ScanlinePainter({
    required this.scroll,
    required this.lineSpacing,
    required this.lineOpacity,
    required this.showSweep,
    required this.sweepProgress,
  });

  final double scroll;
  final double lineSpacing;
  final double lineOpacity;
  final bool showSweep;
  final double sweepProgress;

  @override
  void paint(Canvas canvas, Size size) {
    final linePaint = Paint()
      ..color = Colors.white.withAlpha((lineOpacity * 255).round())
      ..strokeWidth = 1.0
      ..style = PaintingStyle.stroke;

    // Draw horizontal scanlines, offset by scroll for slow movement
    final offset = (scroll * lineSpacing * 10) % lineSpacing;
    var y = offset - lineSpacing;
    while (y < size.height) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), linePaint);
      y += lineSpacing;
    }

    // Sweep band — bright band traveling top to bottom
    if (showSweep) {
      final sweepY = sweepProgress * size.height;
      const bandHeight = 60.0;

      final sweepPaint = Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Colors.white.withAlpha(0),
            Colors.white.withAlpha(10), // rgba(255,255,255,0.04)
            Colors.white.withAlpha(0),
          ],
          stops: const [0.0, 0.5, 1.0],
        ).createShader(
            Rect.fromLTWH(0, sweepY - bandHeight / 2, size.width, bandHeight));

      canvas.drawRect(
        Rect.fromLTWH(0, sweepY - bandHeight / 2, size.width, bandHeight),
        sweepPaint,
      );
    }
  }

  @override
  bool shouldRepaint(_ScanlinePainter old) =>
      old.scroll != scroll || old.sweepProgress != sweepProgress;
}

// ═════════════════════════════════════════════════════════════════
// Aria3dProgressRing — 3D tilted arc progress indicator
// ═════════════════════════════════════════════════════════════════

class Aria3dProgressRing extends StatefulWidget {
  const Aria3dProgressRing({
    super.key,
    required this.progress,
    this.size = 80.0,
    this.color = AriaTheme.brandIndigo,
    this.strokeWidth = 3.0,
    this.label = '',
  });

  final double progress; // 0.0–1.0
  final double size;
  final Color color;
  final double strokeWidth;
  final String label;

  @override
  State<Aria3dProgressRing> createState() => _Aria3dProgressRingState();
}

class _Aria3dProgressRingState extends State<Aria3dProgressRing>
    with SingleTickerProviderStateMixin {
  late final AnimationController _glowCtrl;
  late final Animation<double> _glowAnim;

  @override
  void initState() {
    super.initState();
    _glowCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1800),
    )..repeat(reverse: true);

    _glowAnim = Tween<double>(begin: 0.6, end: 1.0).animate(
        CurvedAnimation(parent: _glowCtrl, curve: Curves.easeInOut));
  }

  @override
  void dispose() {
    _glowCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // 3D disc illusion — tilt on X axis
    final tiltMatrix = Matrix4.identity()
      ..setEntry(3, 2, 0.001)
      ..rotateX(0.3);

    return Transform(
      transform: tiltMatrix,
      alignment: Alignment.center,
      child: AnimatedBuilder(
        animation: _glowAnim,
        builder: (_, __) {
          return SizedBox(
            width: widget.size,
            height: widget.size,
            child: CustomPaint(
              painter: _ProgressRingPainter(
                progress: widget.progress,
                color: widget.color,
                strokeWidth: widget.strokeWidth,
                glowIntensity: _glowAnim.value,
              ),
              child: Center(
                child: widget.label.isNotEmpty
                    ? Text(
                        widget.label,
                        style: AriaTheme.inter(
                          size: widget.size * 0.16,
                          weight: FontWeight.w500,
                          color: AriaTheme.textPrimary,
                          height: 1.0,
                        ),
                        textAlign: TextAlign.center,
                      )
                    : null,
              ),
            ),
          );
        },
      ),
    );
  }
}

class _ProgressRingPainter extends CustomPainter {
  const _ProgressRingPainter({
    required this.progress,
    required this.color,
    required this.strokeWidth,
    required this.glowIntensity,
  });

  final double progress;
  final Color color;
  final double strokeWidth;
  final double glowIntensity;

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    final radius = math.min(cx, cy) - strokeWidth / 2;

    // Background track
    final trackPaint = Paint()
      ..color = Colors.white.withAlpha(20) // rgba(255,255,255,0.08)
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;

    canvas.drawCircle(Offset(cx, cy), radius, trackPaint);

    if (progress <= 0) return;

    // Progress arc with gradient stroke
    final sweepAngle = progress * 2 * math.pi;
    const startAngle = -math.pi / 2; // start at top

    final rect = Rect.fromCircle(center: Offset(cx, cy), radius: radius);

    final gradientPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..shader = SweepGradient(
        startAngle: startAngle,
        endAngle: startAngle + sweepAngle,
        colors: [
          AriaTheme.brandIndigo.withAlpha(180),
          AriaTheme.accentViolet,
        ],
        tileMode: TileMode.clamp,
      ).createShader(rect);

    canvas.drawArc(rect, startAngle, sweepAngle, false, gradientPaint);

    // Glow at arc tip
    final tipAngle = startAngle + sweepAngle;
    final tipX = cx + radius * math.cos(tipAngle);
    final tipY = cy + radius * math.sin(tipAngle);

    final glowAlpha = (glowIntensity * 120).round();
    final glowPaint = Paint()
      ..color = AriaTheme.accentViolet.withAlpha(glowAlpha)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, strokeWidth * 2.5);

    canvas.drawCircle(Offset(tipX, tipY), strokeWidth * 1.2, glowPaint);

    // Bright dot at tip
    final dotPaint = Paint()
      ..color = Colors.white.withAlpha(220)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(tipX, tipY), strokeWidth * 0.6, dotPaint);
  }

  @override
  bool shouldRepaint(_ProgressRingPainter old) =>
      old.progress != progress ||
      old.color != color ||
      old.glowIntensity != glowIntensity;
}
