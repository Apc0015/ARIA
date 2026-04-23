// DESIGN SYSTEM: Linear-inspired dark design (see /DESIGN.md)
// Backgrounds: #08090a → #0f1011 → #191a1b → #28282c
// Brand: #5e6ad2 (indigo) / #7170ff (accent) — CTAs and active states ONLY
// Borders: rgba(255,255,255,0.05) subtle / rgba(255,255,255,0.08) standard
// Typography: Inter Variable, weight 500 as signature emphasis

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AriaTheme {
  // ── Backgrounds (dark → light) ──────────────────────────────
  static const bg0 = Color(0xFF08090A); // deepest canvas
  static const bg1 = Color(0xFF0F1011); // sidebar, topbar, panels
  static const bg2 = Color(0xFF191A1B); // elevated surfaces, cards
  static const bg3 = Color(0xFF28282C); // hover states, secondary surfaces

  // ── Text ───────────────────────────────────────────────────
  static const textPrimary   = Color(0xFFF7F8F8); // near-white (not pure white)
  static const textSecondary = Color(0xFFD0D6E0); // silver-gray body
  static const textMuted     = Color(0xFF8A8F98); // placeholders, metadata
  static const textSubtle    = Color(0xFF62666D); // timestamps, disabled

  // ── Brand — use ONLY for CTAs and active states ────────────
  static const brandIndigo  = Color(0xFF5E6AD2);
  static const accentViolet = Color(0xFF7170FF);
  static const accentHover  = Color(0xFF828FFF);

  // ── Status ─────────────────────────────────────────────────
  static const statusGreen   = Color(0xFF27A644);
  static const statusEmerald = Color(0xFF10B981);
  static const statusRed     = Color(0xFFDC2626);
  static const statusAmber   = Color(0xFFF59E0B);

  // ── Borders (semi-transparent white — never solid on dark) ─
  static const borderSubtle   = Color(0x0DFFFFFF); // rgba(255,255,255,0.05)
  static const borderStandard = Color(0x14FFFFFF); // rgba(255,255,255,0.08)
  static const borderPrimary  = Color(0xFF23252A); // solid dark border

  // ── Card surfaces ──────────────────────────────────────────
  static const cardBg      = Color(0x05FFFFFF); // rgba(255,255,255,0.02)
  static const cardBgHover = Color(0x0AFFFFFF); // rgba(255,255,255,0.04)

  // ── Legacy aliases for backward compat ────────────────────
  // (referenced in widgets not yet migrated)
  static const ocean = brandIndigo;
  static const pine  = statusGreen;
  static const coral = statusRed;
  static const gold  = statusAmber;

  // ── Glass surfaces — frosted panels over star field ───────
  static const glass0     = Color(0x0AFFFFFF); // rgba(255,255,255,0.04) — subtle glass
  static const glass1     = Color(0x12FFFFFF); // rgba(255,255,255,0.07) — light glass
  static const glass2     = Color(0x1AFFFFFF); // rgba(255,255,255,0.10) — medium glass
  static const glassHover = Color(0x22FFFFFF); // rgba(255,255,255,0.13) — hover

  // ── Glass borders — luminous edges ────────────────────────
  static const glassBorder0 = Color(0x14FFFFFF); // rgba(255,255,255,0.08)
  static const glassBorder1 = Color(0x22FFFFFF); // rgba(255,255,255,0.13)
  static const glassBorder2 = Color(0x33FFFFFF); // rgba(255,255,255,0.20)

  // ── Neural glow palette — source node colors ──────────────
  static const glowBlue   = Color(0xFF3B82F6); // web source
  static const glowPurple = Color(0xFF8B5CF6); // academic
  static const glowCyan   = Color(0xFF06B6D4); // social/reddit
  static const glowOrange = Color(0xFFF97316); // youtube/media
  static const glowPink   = Color(0xFFEC4899); // news
  static const glowTeal   = Color(0xFF14B8A6); // rss/podcast
  static const glowAmber  = Color(0xFFF59E0B); // pdf/documents (same as statusAmber)

  // ── Responsive breakpoints ────────────────────────────────
  static const mobileMax = 600.0; // < 600 = mobile
  static const tabletMax = 900.0; // 600–900 = tablet
  // > 900 = desktop

  static bool isMobile(BuildContext ctx)  => MediaQuery.sizeOf(ctx).width < mobileMax;
  static bool isTablet(BuildContext ctx)  => MediaQuery.sizeOf(ctx).width >= mobileMax && MediaQuery.sizeOf(ctx).width < tabletMax;
  static bool isDesktop(BuildContext ctx) => MediaQuery.sizeOf(ctx).width >= tabletMax;

  // ── Animation durations ───────────────────────────────────
  static const durFast   = Duration(milliseconds: 120);
  static const durNormal = Duration(milliseconds: 280);
  static const durSlow   = Duration(milliseconds: 500);
  static const durOrbit  = Duration(milliseconds: 2400); // orbital spin
  static const durPulse  = Duration(milliseconds: 900);  // node pulse

  // ── Animation curves ──────────────────────────────────────
  static const curveSnap   = Curves.easeOut;
  static const curveSpring = Curves.easeInOutCubic;
  static const curveOrbit  = Curves.linear;

  // ── Neural Cosmos gradient helpers ────────────────────────

  /// Radial glow gradient for node backgrounds.
  static RadialGradient nodeGlow(Color color) => RadialGradient(
    colors: [color.withAlpha(60), color.withAlpha(0)],
    radius: 1.0,
  );

  /// Glassmorphism box decoration helper.
  static BoxDecoration glassDecoration({
    Color border = glassBorder1,
    Color surface = glass1,
    double radius = 12,
    Color? glow,
  }) => BoxDecoration(
    color: surface,
    borderRadius: BorderRadius.circular(radius),
    border: Border.all(color: border),
    boxShadow: glow != null
        ? [BoxShadow(color: glow.withAlpha(30), blurRadius: 20, spreadRadius: 0)]
        : null,
  );

  // ── Typography helper ──────────────────────────────────────
  static TextStyle inter({
    double size = 14,
    FontWeight weight = FontWeight.w400,
    Color color = textSecondary,
    double? letterSpacing,
    double height = 1.5,
  }) {
    return GoogleFonts.inter(
      fontSize: size,
      fontWeight: weight,
      color: color,
      letterSpacing: letterSpacing,
      height: height,
      fontFeatures: const [
        FontFeature('cv01'), // alternate single-story 'a'
        FontFeature('ss03'), // geometric letterform adjustments
      ],
    );
  }

  /// IBM Plex Mono — for all numeric data, IDs, percentages, timestamps.
  /// Creates the "precision instrument" signal that differentiates data from prose.
  static TextStyle mono({
    double size = 13,
    FontWeight weight = FontWeight.w400,
    Color color = textSecondary,
    double? letterSpacing,
    double height = 1.5,
  }) => GoogleFonts.ibmPlexMono(
    fontSize: size,
    fontWeight: weight,
    color: color,
    letterSpacing: letterSpacing ?? -0.2,
    height: height,
  );

  /// Syne — for hero text, step titles, page headings.
  /// Geometric, confident, unmistakably crafted — not a default font.
  static TextStyle display({
    double size = 28,
    FontWeight weight = FontWeight.w600,
    Color color = textPrimary,
    double? letterSpacing,
    double height = 1.15,
  }) => GoogleFonts.syne(
    fontSize: size,
    fontWeight: weight,
    color: color,
    letterSpacing: letterSpacing ?? -0.8,
    height: height,
  );

  static ThemeData dark() {
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: bg0,
      colorScheme: ColorScheme.dark(
        primary: brandIndigo,
        secondary: accentViolet,
        surface: bg1,
        surfaceContainerHighest: bg2,
        onPrimary: textPrimary,
        onSecondary: textPrimary,
        onSurface: textPrimary,
        onSurfaceVariant: textMuted,
        outline: borderStandard,
        error: statusRed,
        tertiary: statusEmerald,
      ),
      useMaterial3: true,

      // ── Text theme ────────────────────────────────────────
      textTheme: TextTheme(
        // Display (hero headlines)
        displayLarge:  inter(size: 48, weight: FontWeight.w500, color: textPrimary, letterSpacing: -1.056, height: 1.0),
        displayMedium: inter(size: 32, weight: FontWeight.w400, color: textPrimary, letterSpacing: -0.704, height: 1.13),
        displaySmall:  inter(size: 24, weight: FontWeight.w400, color: textPrimary, letterSpacing: -0.288, height: 1.33),
        // Headings
        headlineLarge:  inter(size: 20, weight: FontWeight.w600, color: textPrimary, letterSpacing: -0.24, height: 1.33),
        headlineMedium: inter(size: 18, weight: FontWeight.w400, color: textPrimary, letterSpacing: -0.165, height: 1.60),
        headlineSmall:  inter(size: 16, weight: FontWeight.w400, color: textPrimary, height: 1.5),
        // Titles (navigation, labels, card headers — signature w500)
        titleLarge:  inter(size: 16, weight: FontWeight.w500, color: textPrimary, height: 1.5),
        titleMedium: inter(size: 15, weight: FontWeight.w500, color: textPrimary, letterSpacing: -0.165, height: 1.6),
        titleSmall:  inter(size: 14, weight: FontWeight.w500, color: textPrimary, letterSpacing: -0.182, height: 1.5),
        // Body
        bodyLarge:  inter(size: 15, weight: FontWeight.w400, color: textSecondary, letterSpacing: -0.165, height: 1.6),
        bodyMedium: inter(size: 14, weight: FontWeight.w400, color: textSecondary, height: 1.5),
        bodySmall:  inter(size: 13, weight: FontWeight.w400, color: textMuted, letterSpacing: -0.13, height: 1.5),
        // Labels (captions, metadata, tiny UI text)
        labelLarge:  inter(size: 13, weight: FontWeight.w500, color: textMuted, letterSpacing: -0.13, height: 1.5),
        labelMedium: inter(size: 12, weight: FontWeight.w500, color: textSubtle, height: 1.4),
        labelSmall:  inter(size: 11, weight: FontWeight.w500, color: textSubtle, height: 1.4),
      ),

      // ── Input fields ──────────────────────────────────────
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: cardBg,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: const BorderSide(color: borderStandard),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: const BorderSide(color: borderStandard),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: const BorderSide(color: brandIndigo),
        ),
        hintStyle: inter(size: 14, color: textSubtle),
        labelStyle: inter(size: 12, weight: FontWeight.w500, color: textMuted),
        prefixIconColor: textSubtle,
        suffixIconColor: textSubtle,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        isDense: true,
      ),

      // ── Cards ─────────────────────────────────────────────
      cardTheme: const CardThemeData(
        elevation: 0,
        margin: EdgeInsets.zero,
        color: bg2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(8)),
          side: BorderSide(color: borderStandard),
        ),
      ),

      // ── Dividers ──────────────────────────────────────────
      dividerTheme: const DividerThemeData(
        color: borderSubtle,
        thickness: 1,
        space: 1,
      ),

      // ── Switch ────────────────────────────────────────────
      switchTheme: SwitchThemeData(
        trackColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) return brandIndigo;
          return bg3;
        }),
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) return textPrimary;
          return textMuted;
        }),
        overlayColor: WidgetStateProperty.all(Colors.transparent),
        trackOutlineColor: WidgetStateProperty.all(Colors.transparent),
      ),

      // ── Slider ────────────────────────────────────────────
      sliderTheme: const SliderThemeData(
        activeTrackColor: brandIndigo,
        inactiveTrackColor: bg3,
        thumbColor: textPrimary,
        overlayColor: Color(0x1A5E6AD2),
        trackHeight: 2,
        thumbShape: RoundSliderThumbShape(enabledThumbRadius: 6),
        valueIndicatorColor: bg2,
        valueIndicatorTextStyle: TextStyle(color: textPrimary, fontSize: 12),
      ),

      // ── Checkbox ──────────────────────────────────────────
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) return brandIndigo;
          return Colors.transparent;
        }),
        checkColor: WidgetStateProperty.all(textPrimary),
        side: const BorderSide(color: borderStandard, width: 1),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(3)),
      ),

      // ── SegmentedButton ───────────────────────────────────
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.selected)) return brandIndigo;
            return cardBg;
          }),
          foregroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.selected)) return textPrimary;
            return textMuted;
          }),
          side: WidgetStateProperty.all(const BorderSide(color: borderStandard)),
          textStyle: WidgetStateProperty.all(
            GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w500),
          ),
        ),
      ),

      // ── Scrollbar ─────────────────────────────────────────
      scrollbarTheme: ScrollbarThemeData(
        thumbColor: WidgetStateProperty.all(bg3),
        radius: const Radius.circular(4),
        thickness: WidgetStateProperty.all(4),
      ),

      // ── AppBar ─────────────────────────────────────────────
      appBarTheme: const AppBarTheme(
        backgroundColor: bg1,
        foregroundColor: textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0,
        surfaceTintColor: Colors.transparent,
      ),

      // ── Chips ─────────────────────────────────────────────
      chipTheme: ChipThemeData(
        backgroundColor: cardBg,
        selectedColor: const Color(0x1A5E6AD2),
        side: const BorderSide(color: borderStandard),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
        labelStyle: GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w500, color: textSecondary),
        padding: const EdgeInsets.symmetric(horizontal: 4),
      ),

      // ── PopupMenu ─────────────────────────────────────────
      popupMenuTheme: const PopupMenuThemeData(
        color: bg2,
        elevation: 8,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(8)),
          side: BorderSide(color: borderStandard),
        ),
      ),
    );
  }
}
