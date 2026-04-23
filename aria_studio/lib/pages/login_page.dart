// ARIA Studio — Login Page
// Dora.run-inspired: bold hero title, minimal glass card, safe 3D hover

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import '../state/aria_controller.dart';
import '../theme/aria_theme.dart';
import '../widgets/effects_3d.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage>
    with SingleTickerProviderStateMixin {
  final _apiUrlCtrl = TextEditingController(text: 'http://127.0.0.1:8765');
  bool _connecting = false;
  String _error = '';

  late final AnimationController _fadeCtrl;
  late final Animation<double> _fadeAnim;
  late final Animation<Offset> _slideAnim;

  @override
  void initState() {
    super.initState();
    _fadeCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
    _fadeAnim = CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeOut);
    _slideAnim = Tween<Offset>(begin: const Offset(0, 0.06), end: Offset.zero)
        .animate(CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeOut));
    _fadeCtrl.forward();
  }

  @override
  void dispose() {
    _fadeCtrl.dispose();
    _apiUrlCtrl.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    final url = _apiUrlCtrl.text.trim();
    if (url.isEmpty) {
      setState(() => _error = 'Enter the ARIA API server URL');
      return;
    }
    setState(() { _connecting = true; _error = ''; });
    final c = context.read<AriaController>();
    c.updateApiBaseUrl(url);
    await c.refreshConnection();
    if (c.isConnected) {
      if (mounted) Navigator.of(context).pushReplacementNamed('/home');
    } else {
      if (mounted) setState(() { _connecting = false; _error = 'Cannot reach ARIA at $url'; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AriaTheme.bg0,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // Star field
          const Aria3dStarField(),

          // Ambient orbs — purely decorative, far from interactive elements
          const Aria3dFloatingOrb(size: 600, color: AriaTheme.brandIndigo, opacity: 0.08,
            top: -200, left: -180,
            driftAmplitude: 24, driftDuration: Duration(seconds: 10)),
          const Aria3dFloatingOrb(size: 500, color: AriaTheme.accentViolet, opacity: 0.06,
            bottom: -200, right: -160,
            driftAmplitude: 18, driftDuration: Duration(seconds: 13)),

          // Main content
          Center(
            child: FadeTransition(
              opacity: _fadeAnim,
              child: SlideTransition(
                position: _slideAnim,
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 60),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // Icon badge
                      Container(
                        width: 52, height: 52,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(14),
                          color: AriaTheme.brandIndigo.withAlpha(28),
                          border: Border.all(color: AriaTheme.brandIndigo.withAlpha(70)),
                        ),
                        child: const Icon(Icons.manage_search_rounded, color: AriaTheme.brandIndigo, size: 24),
                      ),
                      const SizedBox(height: 28),

                      // ARIA — large Dora-style hero title
                      ShaderMask(
                        shaderCallback: (r) => const LinearGradient(
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                          colors: [Color(0xFFFFFFFF), Color(0xFFC7D2FE), Color(0xFF7170FF)],
                          stops: [0.0, 0.5, 1.0],
                        ).createShader(r),
                        blendMode: BlendMode.srcIn,
                        child: Text(
                          'ARIA',
                          style: AriaTheme.inter(
                            size: 72,
                            weight: FontWeight.w900,
                            color: Colors.white,
                            letterSpacing: -4.0,
                            height: 1.0,
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),

                      // Subtitle
                      Text(
                        'Agentic Research Intelligence Architecture',
                        style: AriaTheme.inter(size: 13, color: AriaTheme.textSubtle, letterSpacing: 0.2),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 40),

                      // Login card — glass, no 3D tilt (prevents disappearing)
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 380),
                        child: _LoginCard(
                          apiUrlCtrl: _apiUrlCtrl,
                          connecting: _connecting,
                          error: _error,
                          onConnect: _connect,
                        ),
                      ),
                      const SizedBox(height: 48),
                    ],
                  ),
                ),
              ),
            ),
          ),

          // Version badge
          Positioned(
            bottom: 20, right: 20,
            child: _VersionBadge(),
          ),
        ],
      ),
    );
  }
}

// ── Login card — glassmorphism, hover glow only (no 3D tilt on form)
class _LoginCard extends StatefulWidget {
  const _LoginCard({
    required this.apiUrlCtrl,
    required this.connecting,
    required this.error,
    required this.onConnect,
  });
  final TextEditingController apiUrlCtrl;
  final bool connecting;
  final String error;
  final VoidCallback onConnect;

  @override
  State<_LoginCard> createState() => _LoginCardState();
}

class _LoginCardState extends State<_LoginCard> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.basic,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          color: const Color(0x0AFFFFFF),
          border: Border.all(
            color: _hover
                ? AriaTheme.brandIndigo.withAlpha(80)
                : const Color(0x18FFFFFF),
            width: 1.0,
          ),
          boxShadow: [
            if (_hover)
              BoxShadow(
                color: AriaTheme.brandIndigo.withAlpha(30),
                blurRadius: 40,
                spreadRadius: 4,
              ),
            BoxShadow(
              color: Colors.black.withAlpha(60),
              blurRadius: 20,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        padding: const EdgeInsets.all(32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Connect to ARIA',
              style: AriaTheme.inter(size: 18, weight: FontWeight.w700, color: AriaTheme.textPrimary, letterSpacing: -0.4),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 4),
            Text(
              'Enter your API server URL to continue',
              style: AriaTheme.inter(size: 13, color: AriaTheme.textMuted),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 28),

            _GlowField(controller: widget.apiUrlCtrl, onSubmit: (_) => widget.onConnect()),

            if (widget.error.isNotEmpty) ...[
              const SizedBox(height: 10),
              _ErrorBanner(message: widget.error),
            ],
            const SizedBox(height: 20),

            _ConnectButton(loading: widget.connecting, onTap: widget.onConnect),
            const SizedBox(height: 18),

            SelectableText(
              'python -m aria.cli --serve-api --api-port 8765',
              style: GoogleFonts.sourceCodePro(fontSize: 10, color: AriaTheme.textSubtle, height: 1.6),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

// ── Connect button — hover changes glow intensity, cursor is always pointer
class _ConnectButton extends StatefulWidget {
  const _ConnectButton({required this.loading, required this.onTap});
  final bool loading;
  final VoidCallback onTap;

  @override
  State<_ConnectButton> createState() => _ConnectButtonState();
}

class _ConnectButtonState extends State<_ConnectButton> {
  bool _hover = false;
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() { _hover = false; _pressed = false; }),
      child: GestureDetector(
        onTapDown: (_) => setState(() => _pressed = true),
        onTapUp: (_) { setState(() => _pressed = false); widget.onTap(); },
        onTapCancel: () => setState(() => _pressed = false),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          curve: Curves.easeOut,
          transform: Matrix4.identity()..scale(_pressed ? 0.97 : 1.0),
          transformAlignment: Alignment.center,
          padding: const EdgeInsets.symmetric(vertical: 14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(10),
            color: AriaTheme.brandIndigo,
            boxShadow: [
              BoxShadow(
                color: AriaTheme.brandIndigo.withAlpha(_hover ? 120 : 70),
                blurRadius: _hover ? 30 : 16,
                spreadRadius: _hover ? 2 : 0,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: widget.loading
              ? const Center(child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)))
              : Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text('Connect', style: AriaTheme.inter(size: 14, weight: FontWeight.w600, color: Colors.white)),
                    const SizedBox(width: 8),
                    const Icon(Icons.arrow_forward_rounded, color: Colors.white, size: 16),
                  ],
                ),
        ),
      ),
    );
  }
}

// ── Glow input field
class _GlowField extends StatefulWidget {
  const _GlowField({required this.controller, this.onSubmit});
  final TextEditingController controller;
  final ValueChanged<String>? onSubmit;

  @override
  State<_GlowField> createState() => _GlowFieldState();
}

class _GlowFieldState extends State<_GlowField> {
  final _focus = FocusNode();
  bool _focused = false;

  @override
  void initState() {
    super.initState();
    _focus.addListener(() => setState(() => _focused = _focus.hasFocus));
  }

  @override
  void dispose() { _focus.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(10),
        color: _focused ? const Color(0x145E6AD2) : const Color(0x08FFFFFF),
        border: Border.all(
          color: _focused ? AriaTheme.brandIndigo : const Color(0x18FFFFFF),
          width: _focused ? 1.5 : 1.0,
        ),
        boxShadow: _focused
            ? [BoxShadow(color: AriaTheme.brandIndigo.withAlpha(40), blurRadius: 16, spreadRadius: 2)]
            : [],
      ),
      child: TextField(
        controller: widget.controller,
        focusNode: _focus,
        onSubmitted: widget.onSubmit,
        style: AriaTheme.inter(size: 14, color: AriaTheme.textPrimary),
        decoration: InputDecoration(
          hintText: 'http://127.0.0.1:8765',
          hintStyle: AriaTheme.inter(size: 14, color: AriaTheme.textSubtle),
          prefixIcon: Icon(Icons.dns_outlined, size: 16, color: _focused ? AriaTheme.brandIndigo : AriaTheme.textSubtle),
          border: InputBorder.none,
          enabledBorder: InputBorder.none,
          focusedBorder: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
          isDense: true,
        ),
      ),
    );
  }
}

// ── Error banner
class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AriaTheme.statusRed.withAlpha(25),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AriaTheme.statusRed.withAlpha(60)),
      ),
      child: Text(message, style: AriaTheme.inter(size: 12, color: AriaTheme.statusRed), textAlign: TextAlign.center),
    );
  }
}

// ── Version badge
class _VersionBadge extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(999),
        color: Colors.white.withAlpha(8),
        border: Border.all(color: Colors.white.withAlpha(15)),
      ),
      child: Text('v4.1.0', style: AriaTheme.inter(size: 11, weight: FontWeight.w500, color: AriaTheme.textSubtle)),
    );
  }
}
