// Neural Cosmos widget library — glassmorphism, glow nodes, preset cards,
// and responsive layout for ARIA Studio.

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/aria_theme.dart';

// ─────────────────────────────────────────────────────────────────────────────
// 1. GlassPanel
// ─────────────────────────────────────────────────────────────────────────────

/// Frosted glassmorphism card that replaces [AriaCard] for the Neural Cosmos
/// design. Uses the glass tokens from [AriaTheme].
///
/// ```dart
/// GlassPanel(child: ..., glow: AriaTheme.glowBlue)
/// ```
class GlassPanel extends StatelessWidget {
  const GlassPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(20),
    this.glow,
    this.radius = 12.0,
    this.surface,
  });

  final Widget child;
  final EdgeInsets padding;

  /// Optional edge-glow color (e.g. [AriaTheme.glowBlue]).
  final Color? glow;

  final double radius;

  /// Defaults to [AriaTheme.glass1] when null.
  final Color? surface;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: AriaTheme.glassDecoration(
        surface: surface ?? AriaTheme.glass1,
        radius: radius,
        glow: glow,
      ),
      child: child,
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. GlowNode
// ─────────────────────────────────────────────────────────────────────────────

/// Animated pulsing circle representing a data source.
/// Used in source-visualization and run-status views.
///
/// ```dart
/// GlowNode(color: AriaTheme.glowBlue, label: 'Web', active: true, size: 48)
/// ```
class GlowNode extends StatefulWidget {
  const GlowNode({
    super.key,
    required this.color,
    this.label,
    this.active = false,
    this.size = 40.0,
    this.onTap,
  });

  final Color color;

  /// Optional label rendered below the node.
  final String? label;

  /// When true, the outer ring pulses continuously.
  final bool active;

  final double size;
  final VoidCallback? onTap;

  @override
  State<GlowNode> createState() => _GlowNodeState();
}

class _GlowNodeState extends State<GlowNode>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _scale;
  late final Animation<double> _opacity;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: AriaTheme.durPulse,
    );

    _scale = Tween<double>(begin: 1.0, end: 1.3).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );
    _opacity = Tween<double>(begin: 1.0, end: 0.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeIn),
    );

    if (widget.active) {
      _controller.repeat(reverse: false);
    }
  }

  @override
  void didUpdateWidget(GlowNode oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.active != oldWidget.active) {
      if (widget.active) {
        _controller.repeat(reverse: false);
      } else {
        _controller.stop();
        _controller.reset();
      }
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Widget _buildNode() {
    return SizedBox(
      width: widget.size,
      height: widget.size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Outer pulsing ring (active only)
          if (widget.active)
            AnimatedBuilder(
              animation: _controller,
              builder: (context, _) {
                return Transform.scale(
                  scale: _scale.value,
                  child: Container(
                    width: widget.size,
                    height: widget.size,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: widget.color
                            .withAlpha((_opacity.value * 100).round()),
                        width: 1.5,
                      ),
                    ),
                  ),
                );
              },
            ),

          // Static background circle
          Container(
            width: widget.size,
            height: widget.size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: widget.color.withAlpha(widget.active ? 40 : 20),
              border: Border.all(
                color: widget.color.withAlpha(widget.active ? 100 : 50),
                width: 1,
              ),
            ),
          ),

          // Inner dot
          Container(
            width: widget.size * 0.4,
            height: widget.size * 0.4,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: widget.color.withAlpha(widget.active ? 200 : 120),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    Widget content = Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        _buildNode(),
        if (widget.label != null) ...[
          const SizedBox(height: 6),
          Text(
            widget.label!,
            style: AriaTheme.inter(
              size: 10,
              color: AriaTheme.textSubtle,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ],
    );

    if (widget.onTap != null) {
      content = MouseRegion(
        cursor: SystemMouseCursors.click,
        child: GestureDetector(
          onTap: widget.onTap,
          child: content,
        ),
      );
    }

    return content;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. PresetCard
// ─────────────────────────────────────────────────────────────────────────────

/// Selectable 3-D–tilt card for choosing a research preset
/// (Quick / Deep / Academic).
///
/// ```dart
/// PresetCard(
///   icon: Icons.flash_on,
///   title: 'Quick Scan',
///   subtitle: '5–10 sources, ~2 min',
///   color: AriaTheme.glowCyan,
///   selected: _preset == 'quick',
///   onTap: () => setState(() => _preset = 'quick'),
/// )
/// ```
class PresetCard extends StatefulWidget {
  const PresetCard({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.color,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final bool selected;
  final VoidCallback onTap;

  @override
  State<PresetCard> createState() => _PresetCardState();
}

class _PresetCardState extends State<PresetCard>
    with SingleTickerProviderStateMixin {
  bool _hover = false;
  double _mouseX = 0;
  double _mouseY = 0;

  // Max 5° tilt = 5 * pi/180 radians
  static const double _maxTilt = 5.0 * math.pi / 180.0;

  void _onHover(PointerEvent event, BoxConstraints constraints) {
    final dx = event.localPosition.dx;
    final dy = event.localPosition.dy;
    final cx = constraints.maxWidth / 2;
    final cy = constraints.maxHeight / 2;
    setState(() {
      _hover = true;
      // Normalise to [-1, 1] then scale to max tilt
      _mouseX = ((dx - cx) / cx).clamp(-1.0, 1.0) * _maxTilt;
      _mouseY = ((dy - cy) / cy).clamp(-1.0, 1.0) * _maxTilt;
    });
  }

  void _onExit() {
    setState(() {
      _hover = false;
      _mouseX = 0;
      _mouseY = 0;
    });
  }

  @override
  Widget build(BuildContext context) {
    final tiltX = _hover ? _mouseX : 0.0;
    final tiltY = _hover ? _mouseY : 0.0;

    return LayoutBuilder(
      builder: (context, constraints) {
        return MouseRegion(
          cursor: SystemMouseCursors.click,
          onHover: (e) => _onHover(e, constraints),
          onExit: (_) => _onExit(),
          child: GestureDetector(
            onTap: widget.onTap,
            child: Transform(
              transform: Matrix4.identity()
                ..setEntry(3, 2, 0.001)
                ..rotateX(-tiltY)
                ..rotateY(tiltX),
              alignment: Alignment.center,
              child: AnimatedContainer(
                duration: AriaTheme.durFast,
                curve: AriaTheme.curveSnap,
                constraints: const BoxConstraints(minWidth: 140),
                decoration: AriaTheme.glassDecoration(
                  surface: widget.selected
                      ? widget.color.withAlpha(20)
                      : (_hover ? AriaTheme.glassHover : AriaTheme.glass1),
                  radius: 12,
                  glow: widget.selected ? widget.color : null,
                  border: widget.selected
                      ? widget.color.withAlpha(40)
                      : AriaTheme.glassBorder1,
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Stack(
                    children: [
                      // Card content
                      Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(widget.icon, size: 24, color: widget.color),
                            const SizedBox(height: 10),
                            Text(
                              widget.title,
                              style: AriaTheme.inter(
                                size: 13,
                                weight: FontWeight.w500,
                                color: AriaTheme.textPrimary,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              widget.subtitle,
                              style: AriaTheme.inter(
                                size: 11,
                                color: AriaTheme.textMuted,
                              ),
                            ),
                          ],
                        ),
                      ),

                      // Selected: indigo bottom accent line
                      if (widget.selected)
                        Positioned(
                          left: 0,
                          right: 0,
                          bottom: 0,
                          child: Container(
                            height: 3,
                            decoration: BoxDecoration(
                              color: AriaTheme.brandIndigo,
                              borderRadius: const BorderRadius.only(
                                bottomLeft: Radius.circular(12),
                                bottomRight: Radius.circular(12),
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. ResponsiveLayout
// ─────────────────────────────────────────────────────────────────────────────

/// Renders different children based on screen width breakpoints defined in
/// [AriaTheme.mobileMax] and [AriaTheme.tabletMax].
///
/// ```dart
/// ResponsiveLayout(
///   mobile: MobileContent(),
///   tablet: TabletContent(),   // optional — falls back to mobile when null
///   desktop: DesktopContent(),
/// )
/// ```
class ResponsiveLayout extends StatelessWidget {
  const ResponsiveLayout({
    super.key,
    required this.mobile,
    this.tablet,
    required this.desktop,
  });

  final Widget mobile;

  /// Falls back to [mobile] when null and the screen is tablet-width.
  final Widget? tablet;

  final Widget desktop;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        if (width >= AriaTheme.tabletMax) {
          return desktop;
        } else if (width >= AriaTheme.mobileMax) {
          return tablet ?? mobile;
        } else {
          return mobile;
        }
      },
    );
  }
}
