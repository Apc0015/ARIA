// ARIA Studio — shared design-system widgets
// All follow DESIGN.md (Linear-inspired dark design)
// bg0=#08090a · bg1=#0f1011 · bg2=#191a1b · brand=#5e6ad2
// Borders: rgba(255,255,255,0.05–0.08) · Buttons: translucent ghosts + indigo CTA

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/aria_theme.dart';

// ─────────────────────────────────────────────────────────────
// Top bar — shared across Dashboard and Settings
// ─────────────────────────────────────────────────────────────

class AriaTopBar extends StatelessWidget implements PreferredSizeWidget {
  const AriaTopBar({
    super.key,
    this.leading,
    this.trailing = const [],
    this.title,
  });

  final Widget?       leading;
  final List<Widget>  trailing;
  final Widget?       title;

  @override
  Size get preferredSize => const Size.fromHeight(48);

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 48,
      decoration: const BoxDecoration(
        color: AriaTheme.bg1,
        border: Border(bottom: BorderSide(color: AriaTheme.borderSubtle)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          if (leading != null) ...[leading!, const SizedBox(width: 12)],
          // Default logotype
          if (leading == null) _Logotype(),
          if (title != null) ...[const SizedBox(width: 12), title!],
          const Spacer(),
          ...trailing,
        ],
      ),
    );
  }
}

class _Logotype extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        RichText(
          text: TextSpan(children: [
            TextSpan(
              text: 'ARIA',
              style: AriaTheme.inter(
                size: 14,
                weight: FontWeight.w600,
                color: AriaTheme.textPrimary,
                letterSpacing: 0.4,
              ),
            ),
            TextSpan(
              text: '  Studio',
              style: AriaTheme.inter(size: 13, color: AriaTheme.textMuted),
            ),
          ]),
        ),
        const SizedBox(width: 8),
        AriaPill(label: 'v4.1.0', subtle: true),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Card — bg2 surface, borderStandard, 8px radius
// ─────────────────────────────────────────────────────────────

class AriaCard extends StatelessWidget {
  const AriaCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(20),
    this.color = AriaTheme.bg2,
  });

  final Widget    child;
  final EdgeInsets padding;
  final Color     color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AriaTheme.borderStandard),
      ),
      child: child,
    );
  }
}

// Inner card (rgba 0.02 bg) for nested containers
class AriaInnerCard extends StatelessWidget {
  const AriaInnerCard({super.key, required this.child, this.padding = const EdgeInsets.all(12)});
  final Widget    child;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: AriaTheme.cardBg,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AriaTheme.borderSubtle),
      ),
      child: child,
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Pill badge — 9999px radius, translucent
// ─────────────────────────────────────────────────────────────

class AriaPill extends StatelessWidget {
  const AriaPill({super.key, required this.label, this.color, this.subtle = false});
  final String label;
  final Color? color;
  final bool   subtle;

  @override
  Widget build(BuildContext context) {
    final c = color ?? AriaTheme.textSubtle;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color:  subtle ? AriaTheme.cardBg : c.withAlpha(30),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: subtle ? AriaTheme.borderSubtle : c.withAlpha(60)),
      ),
      child: Text(
        label,
        style: AriaTheme.inter(
          size: 10,
          weight: FontWeight.w500,
          color: subtle ? AriaTheme.textSubtle : c,
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Ghost button — rgba(0.02) bg, borderStandard, 6px radius
// ─────────────────────────────────────────────────────────────

class AriaGhostButton extends StatelessWidget {
  const AriaGhostButton({super.key, required this.label, this.onPressed, this.icon});
  final String    label;
  final VoidCallback? onPressed;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    return GestureDetector(
      onTap: onPressed,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: AriaTheme.cardBg,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: AriaTheme.borderStandard),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(icon, size: 13, color: enabled ? AriaTheme.textSecondary : AriaTheme.textSubtle),
              const SizedBox(width: 6),
            ],
            Text(
              label,
              style: AriaTheme.inter(
                size: 12,
                weight: FontWeight.w500,
                color: enabled ? AriaTheme.textSecondary : AriaTheme.textSubtle,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Primary button — brand indigo, 6px radius
// ─────────────────────────────────────────────────────────────

class AriaPrimaryButton extends StatelessWidget {
  const AriaPrimaryButton({super.key, required this.label, this.onPressed, this.icon, this.loading = false});
  final String    label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool      loading;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null && !loading;
    return GestureDetector(
      onTap: enabled ? onPressed : null,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: enabled ? AriaTheme.brandIndigo : AriaTheme.bg3,
          borderRadius: BorderRadius.circular(6),
        ),
        child: loading
            ? const SizedBox(
                width: 14, height: 14,
                child: CircularProgressIndicator(strokeWidth: 1.5, color: AriaTheme.textPrimary),
              )
            : Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (icon != null) ...[
                    Icon(icon, size: 13, color: enabled ? AriaTheme.textPrimary : AriaTheme.textSubtle),
                    const SizedBox(width: 6),
                  ],
                  Text(
                    label,
                    style: AriaTheme.inter(
                      size: 13,
                      weight: FontWeight.w500,
                      color: enabled ? AriaTheme.textPrimary : AriaTheme.textSubtle,
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Danger button — red, 6px radius
// ─────────────────────────────────────────────────────────────

class AriaDangerButton extends StatelessWidget {
  const AriaDangerButton({super.key, required this.label, this.onPressed});
  final String    label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onPressed,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: AriaTheme.statusRed.withAlpha(20),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: AriaTheme.statusRed.withAlpha(60)),
        ),
        child: Text(
          label,
          style: AriaTheme.inter(size: 12, weight: FontWeight.w500, color: AriaTheme.statusRed),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Tab chip — for mode selection (Cloud/Local etc.)
// ─────────────────────────────────────────────────────────────

class AriaTabChip extends StatelessWidget {
  const AriaTabChip({super.key, required this.label, required this.selected, required this.onTap});
  final String   label;
  final bool     selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
        decoration: BoxDecoration(
          color: selected ? const Color(0x1A5E6AD2) : AriaTheme.cardBg,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: selected ? AriaTheme.brandIndigo : AriaTheme.borderSubtle),
        ),
        child: Text(
          label,
          style: AriaTheme.inter(
            size: 12,
            weight: FontWeight.w500,
            color: selected ? AriaTheme.accentViolet : AriaTheme.textMuted,
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Status dot — green/muted with label
// ─────────────────────────────────────────────────────────────

class AriaStatusDot extends StatelessWidget {
  const AriaStatusDot({super.key, required this.connected, required this.label});
  final bool   connected;
  final String label;

  @override
  Widget build(BuildContext context) {
    final color = connected ? AriaTheme.statusEmerald : AriaTheme.textSubtle;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 6, height: 6,
          decoration: BoxDecoration(shape: BoxShape.circle, color: color),
        ),
        const SizedBox(width: 6),
        Text(label, style: AriaTheme.inter(size: 12, weight: FontWeight.w500, color: color)),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Pulsing dot — for active run state
// ─────────────────────────────────────────────────────────────

class AriaPulseDot extends StatefulWidget {
  const AriaPulseDot({super.key, this.color = AriaTheme.accentViolet});
  final Color color;
  @override
  State<AriaPulseDot> createState() => _AriaPulseDotState();
}

class _AriaPulseDotState extends State<AriaPulseDot> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double>   _anim;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))..repeat(reverse: true);
    _anim = Tween<double>(begin: 0.3, end: 1.0).animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut));
  }

  @override
  void dispose() { _ctrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _anim,
      builder: (_, __) => Container(
        width: 6, height: 6,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: widget.color.withAlpha((_anim.value * 255).round()),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Metric tile — stat card
// ─────────────────────────────────────────────────────────────

class AriaMetricTile extends StatelessWidget {
  const AriaMetricTile({super.key, required this.label, required this.value, this.accent});
  final String label;
  final String value;
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    final c = accent ?? AriaTheme.textMuted;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AriaTheme.cardBg,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: accent != null ? accent!.withAlpha(80) : AriaTheme.borderSubtle),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label, style: AriaTheme.inter(size: 10, color: AriaTheme.textSubtle)),
          const SizedBox(height: 3),
          Text(value, style: AriaTheme.inter(size: 20, weight: FontWeight.w500, color: c, height: 1.1)),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Section header — uppercase label + optional trailing
// ─────────────────────────────────────────────────────────────

class AriaSectionHeader extends StatelessWidget {
  const AriaSectionHeader({super.key, required this.title, this.trailing});
  final String  title;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(
          title.toUpperCase(),
          style: AriaTheme.inter(
            size: 10,
            weight: FontWeight.w600,
            color: AriaTheme.textSubtle,
            letterSpacing: 0.8,
          ),
        ),
        if (trailing != null) ...[const Spacer(), trailing!],
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Collapsible section row
// ─────────────────────────────────────────────────────────────

class AriaCollapseRow extends StatelessWidget {
  const AriaCollapseRow({
    super.key,
    required this.label,
    required this.expanded,
    required this.onTap,
    this.badge,
  });
  final String  label;
  final bool    expanded;
  final VoidCallback onTap;
  final String? badge;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Row(
        children: [
          Icon(
            expanded ? Icons.keyboard_arrow_down : Icons.keyboard_arrow_right,
            size: 14,
            color: AriaTheme.textSubtle,
          ),
          const SizedBox(width: 4),
          Text(label, style: AriaTheme.inter(size: 12, weight: FontWeight.w500, color: AriaTheme.textMuted)),
          if (badge != null) ...[
            const SizedBox(width: 6),
            AriaPill(label: badge!, subtle: true),
          ],
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Input field (DESIGN.md: rgba(0.02) bg, rgba(0.08) border, 6px)
// ─────────────────────────────────────────────────────────────

class AriaInputField extends StatelessWidget {
  const AriaInputField({
    super.key,
    required this.controller,
    this.hint = '',
    this.label,
    this.icon,
    this.obscure = false,
    this.maxLines = 1,
    this.onChanged,
    this.onSubmit,
    this.keyboardType,
    this.enabled = true,
    this.suffix,
  });

  final TextEditingController controller;
  final String  hint;
  final String? label;
  final IconData? icon;
  final bool    obscure;
  final int     maxLines;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmit;
  final TextInputType? keyboardType;
  final bool    enabled;
  final Widget? suffix;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (label != null) ...[
          Text(
            label!,
            style: AriaTheme.inter(size: 11, weight: FontWeight.w500, color: AriaTheme.textMuted),
          ),
          const SizedBox(height: 5),
        ],
        Container(
          decoration: BoxDecoration(
            color: const Color(0x05FFFFFF),
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: AriaTheme.borderStandard),
          ),
          child: TextField(
            controller: controller,
            obscureText: obscure,
            maxLines: maxLines,
            enabled: enabled,
            onChanged: onChanged,
            onSubmitted: onSubmit,
            keyboardType: keyboardType,
            style: AriaTheme.inter(size: 13, color: AriaTheme.textPrimary),
            decoration: InputDecoration(
              hintText: hint,
              hintStyle: AriaTheme.inter(size: 13, color: AriaTheme.textSubtle),
              prefixIcon: icon != null ? Icon(icon, size: 15, color: AriaTheme.textSubtle) : null,
              suffixIcon: suffix,
              border: InputBorder.none,
              enabledBorder: InputBorder.none,
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(6),
                borderSide: const BorderSide(color: AriaTheme.brandIndigo),
              ),
              disabledBorder: InputBorder.none,
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              isDense: true,
            ),
          ),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Source toggle row
// ─────────────────────────────────────────────────────────────

class AriaSourceRow extends StatelessWidget {
  const AriaSourceRow({
    super.key,
    required this.label,
    required this.value,
    required this.onChanged,
    this.icon,
    this.subtitle,
  });
  final String    label;
  final bool      value;
  final ValueChanged<bool> onChanged;
  final IconData? icon;
  final String?   subtitle;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Container(
            width: 5, height: 5,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: value ? AriaTheme.statusEmerald : AriaTheme.textSubtle,
            ),
          ),
          const SizedBox(width: 10),
          if (icon != null) ...[
            Icon(icon, size: 14, color: value ? AriaTheme.textMuted : AriaTheme.textSubtle),
            const SizedBox(width: 8),
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  label,
                  style: AriaTheme.inter(
                    size: 13,
                    color: value ? AriaTheme.textSecondary : AriaTheme.textSubtle,
                  ),
                ),
                if (subtitle != null)
                  Text(subtitle!, style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
              ],
            ),
          ),
          Switch(value: value, onChanged: onChanged),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Mono text — for code/logs/paths
// ─────────────────────────────────────────────────────────────

class AriaMonoText extends StatelessWidget {
  const AriaMonoText(this.text, {super.key, this.size = 12, this.color = AriaTheme.textSecondary});
  final String text;
  final double size;
  final Color  color;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: GoogleFonts.sourceCodePro(fontSize: size, color: color, height: 1.5),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────

String ariaExcerpt(String text, [int maxWords = 30]) {
  if (text.isEmpty) return '';
  final words = text.trim().split(RegExp(r'\s+'));
  if (words.length <= maxWords) return text.trim();
  return '${words.take(maxWords).join(' ')}…';
}
