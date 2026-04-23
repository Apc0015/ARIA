// ARIA Studio — Setup / Onboarding Page
// 4-step wizard: Connect → Topic → Sources → AI Model
// Replaces the login page. No settings page needed after this.

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/aria_controller.dart';
import '../theme/aria_theme.dart';
import '../widgets/effects_3d.dart';
import '../widgets/neural_widgets.dart';
import '../widgets/shared.dart';

class SetupPage extends StatefulWidget {
  const SetupPage({super.key});

  @override
  State<SetupPage> createState() => _SetupPageState();
}

class _SetupPageState extends State<SetupPage>
    with SingleTickerProviderStateMixin {
  int  _step    = 0;
  bool _forward = true; // direction for transition

  late final AnimationController _entranceCtrl;
  late final Animation<double>   _entranceFade;

  @override
  void initState() {
    super.initState();
    _entranceCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 600));
    _entranceFade = CurvedAnimation(
        parent: _entranceCtrl, curve: Curves.easeOut);
    _entranceCtrl.forward();
  }

  @override
  void dispose() {
    _entranceCtrl.dispose();
    super.dispose();
  }

  void _next() => setState(() { _forward = true;  _step++; });
  void _back() => setState(() { _forward = false; _step--; });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AriaTheme.bg0,
      body: FadeTransition(
        opacity: _entranceFade,
        child: Stack(children: [
          const Positioned.fill(
            child: Opacity(opacity: 0.30, child: Aria3dStarField()),
          ),
          Column(children: [
            Expanded(
              child: Center(
                child: AnimatedSwitcher(
                  duration: AriaTheme.durNormal,
                  switchInCurve:  AriaTheme.curveSpring,
                  switchOutCurve: AriaTheme.curveSnap,
                  transitionBuilder: (child, anim) {
                    final offset = _forward
                        ? const Offset(0.06, 0)
                        : const Offset(-0.06, 0);
                    return SlideTransition(
                      position: Tween<Offset>(
                        begin: offset, end: Offset.zero,
                      ).animate(anim),
                      child: FadeTransition(opacity: anim, child: child),
                    );
                  },
                  child: _buildStep(key: ValueKey(_step)),
                ),
              ),
            ),
            _StepDots(current: _step, total: 4),
            const SizedBox(height: 32),
          ]),
        ]),
      ),
    );
  }

  Widget _buildStep({required Key key}) {
    switch (_step) {
      case 0:
        return _ConnectStep(key: key, onNext: _next);
      case 1:
        return _TopicStep(key: key, onNext: _next, onBack: _back);
      case 2:
        return _SourcesStep(key: key, onNext: _next, onBack: _back);
      case 3:
        return _ModelStep(key: key, onBack: _back);
      default:
        return const SizedBox.shrink();
    }
  }
}

// ─────────────────────────────────────────────────────────────
// Step indicator dots
// ─────────────────────────────────────────────────────────────

class _StepDots extends StatelessWidget {
  const _StepDots({required this.current, required this.total});
  final int current, total;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(total, (i) {
        final done   = i < current;
        final active = i == current;
        final color = active
            ? AriaTheme.brandIndigo
            : done
                ? AriaTheme.statusEmerald
                : AriaTheme.textSubtle;
        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 6),
          child: AnimatedOpacity(
            duration: AriaTheme.durNormal,
            opacity: active ? 1.0 : (done ? 0.7 : 0.35),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Container(
                width: 20, height: 20,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: active
                      ? AriaTheme.brandIndigo.withAlpha(20)
                      : Colors.transparent,
                  border: Border.all(
                    color: color.withAlpha(active ? 140 : 60),
                    width: active ? 1.5 : 1,
                  ),
                ),
                child: Center(
                  child: Text('${i + 1}'.padLeft(2, '0'),
                    style: AriaTheme.mono(
                      size: 8, weight: FontWeight.w500, color: color, height: 1)),
                ),
              ),
              if (i < total - 1) ...[
                const SizedBox(width: 4),
                AnimatedContainer(
                  duration: AriaTheme.durNormal,
                  width: 16, height: 1,
                  color: done
                      ? AriaTheme.statusEmerald.withAlpha(60)
                      : AriaTheme.borderSubtle,
                ),
                const SizedBox(width: 4),
              ],
            ]),
          ),
        );
      }),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Shared step wrapper
// ─────────────────────────────────────────────────────────────

class _StepWrapper extends StatelessWidget {
  const _StepWrapper({required this.child, this.maxWidth = 480});
  final Widget child;
  final double maxWidth;

  @override
  Widget build(BuildContext context) {
    final mobile = AriaTheme.isMobile(context);
    if (mobile) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 0),
        child: child,
      );
    }
    return GlassPanel(
      glow: AriaTheme.brandIndigo.withAlpha(60),
      padding: const EdgeInsets.all(32),
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth, minWidth: 320),
        child: child,
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Step 0: Connect
// ─────────────────────────────────────────────────────────────

class _ConnectStep extends StatefulWidget {
  const _ConnectStep({super.key, required this.onNext});
  final VoidCallback onNext;

  @override
  State<_ConnectStep> createState() => _ConnectStepState();
}

class _ConnectStepState extends State<_ConnectStep> {
  late final TextEditingController _urlCtrl;
  bool  _loading  = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final savedUrl = context.read<AriaController>().apiBaseUrl;
    _urlCtrl = TextEditingController(text: savedUrl);
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    final c = context.read<AriaController>();
    setState(() { _loading = true; _error = null; });
    try {
      await c.persistApiUrl(_urlCtrl.text.trim());
      await c.bootstrap();
      if (!mounted) return;
      if (c.isConnected) {
        widget.onNext();
      } else {
        setState(() => _error = 'Could not connect — is the server running?');
      }
    } catch (e) {
      if (mounted) setState(() => _error = 'Connection failed: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return _StepWrapper(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Logo
          Row(children: [
            Text('ARIA', style: AriaTheme.display(
              size: 20, color: AriaTheme.brandIndigo, letterSpacing: 3.5)),
            const SizedBox(width: 10),
            AriaPill(label: 'v5.0', subtle: true),
          ]),
          const SizedBox(height: 24),
          Text('Connect to ARIA', style: AriaTheme.display(size: 26)),
          const SizedBox(height: 6),
          Text('Enter your ARIA server address to get started.',
            style: AriaTheme.inter(size: 14, color: AriaTheme.textMuted)),
          const SizedBox(height: 28),
          AriaInputField(
            controller: _urlCtrl,
            hint: 'http://127.0.0.1:8765',
            label: 'Server URL',
            icon: Icons.dns_outlined,
          ),
          if (_error != null) ...[
            const SizedBox(height: 10),
            Row(children: [
              const Icon(Icons.error_outline, size: 14,
                  color: AriaTheme.statusRed),
              const SizedBox(width: 6),
              Flexible(child: Text(_error!,
                style: AriaTheme.inter(size: 12, color: AriaTheme.statusRed))),
            ]),
          ],
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: AriaPrimaryButton(
              label: 'Connect',
              icon: Icons.arrow_forward,
              loading: _loading,
              onPressed: _loading ? null : _connect,
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Step 1: Research Topic
// ─────────────────────────────────────────────────────────────

class _TopicStep extends StatefulWidget {
  const _TopicStep({super.key, required this.onNext, required this.onBack});
  final VoidCallback onNext, onBack;

  @override
  State<_TopicStep> createState() => _TopicStepState();
}

class _TopicStepState extends State<_TopicStep> {
  final _topicCtrl  = TextEditingController();
  final _intentCtrl = TextEditingController();
  bool  _error      = false;

  @override
  void dispose() {
    _topicCtrl.dispose();
    _intentCtrl.dispose();
    super.dispose();
  }

  void _continue() {
    if (_topicCtrl.text.trim().isEmpty) {
      setState(() => _error = true);
      return;
    }
    final c = context.read<AriaController>();
    c.updateTopic(_topicCtrl.text.trim());
    c.updateIntent(_intentCtrl.text.trim());
    widget.onNext();
  }

  @override
  Widget build(BuildContext context) {
    return _StepWrapper(
      maxWidth: 520,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('What do you want\nto research?', style: AriaTheme.display(size: 26)),
          const SizedBox(height: 28),
          AriaInputField(
            controller: _topicCtrl,
            hint: 'AI safety in healthcare',
            label: 'Research topic',
            icon: Icons.search,
            onChanged: (_) { if (_error) setState(() => _error = false); },
          ),
          if (_error) ...[
            const SizedBox(height: 6),
            Text('Please enter a topic to continue.',
              style: AriaTheme.inter(size: 12, color: AriaTheme.statusRed)),
          ],
          const SizedBox(height: 14),
          AriaInputField(
            controller: _intentCtrl,
            hint: 'Risks of AI diagnostics in clinical settings (optional)',
            label: 'Research intent',
            icon: Icons.lightbulb_outline,
            maxLines: 2,
          ),
          const SizedBox(height: 24),
          Row(children: [
            AriaGhostButton(
                label: 'Back', icon: Icons.arrow_back, onPressed: widget.onBack),
            const SizedBox(width: 10),
            Expanded(child: AriaPrimaryButton(
              label: 'Continue',
              icon: Icons.arrow_forward,
              onPressed: _continue,
            )),
          ]),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Step 2: Sources preset
// ─────────────────────────────────────────────────────────────

class _SourcesStep extends StatefulWidget {
  const _SourcesStep({super.key, required this.onNext, required this.onBack});
  final VoidCallback onNext, onBack;

  @override
  State<_SourcesStep> createState() => _SourcesStepState();
}

class _SourcesStepState extends State<_SourcesStep> {
  String _preset = 'quick';

  void _apply(String preset) {
    setState(() => _preset = preset);
    final c = context.read<AriaController>();
    switch (preset) {
      case 'quick':
        c.toggleSrcWeb(true); c.toggleSrcWikipedia(true);
        c.toggleSrcAcademic(false); c.toggleSrcPdf(false);
        c.toggleSrcYoutube(false); c.toggleSrcReddit(false);
        c.toggleSrcHackernews(false);
      case 'deep':
        c.toggleSrcWeb(true); c.toggleSrcWikipedia(true);
        c.toggleSrcReddit(true); c.toggleSrcHackernews(true);
        c.toggleSrcYoutube(true); c.toggleSrcPdf(true);
        c.toggleSrcAcademic(false);
      case 'academic':
        c.toggleSrcAcademic(true); c.toggleSrcPdf(true); c.toggleSrcWeb(true);
        c.toggleSrcWikipedia(false); c.toggleSrcYoutube(false);
        c.toggleSrcReddit(false); c.toggleSrcHackernews(false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final mobile = AriaTheme.isMobile(context);

    final cards = [
      _PresetDef(
        key: 'quick',
        icon: Icons.bolt,
        title: 'Quick Scan',
        subtitle: 'Web + Wikipedia\n~2 min',
        color: AriaTheme.glowCyan,
      ),
      _PresetDef(
        key: 'deep',
        icon: Icons.travel_explore,
        title: 'Deep Dive',
        subtitle: 'All free sources\n~8 min',
        color: AriaTheme.accentViolet,
      ),
      _PresetDef(
        key: 'academic',
        icon: Icons.school_outlined,
        title: 'Academic',
        subtitle: 'Papers + PDF\n~5 min',
        color: AriaTheme.glowPurple,
      ),
    ];

    return _StepWrapper(
      maxWidth: 580,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Choose research depth', style: AriaTheme.display(size: 26)),
          const SizedBox(height: 6),
          Text('Pick a preset — you can always customize later.',
            style: AriaTheme.inter(size: 14, color: AriaTheme.textMuted)),
          const SizedBox(height: 24),
          if (mobile)
            Column(
              children: cards.map((d) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: SizedBox(
                  width: double.infinity,
                  child: PresetCard(
                    icon: d.icon, title: d.title,
                    subtitle: d.subtitle, color: d.color,
                    selected: _preset == d.key,
                    onTap: () => _apply(d.key),
                  ),
                ),
              )).toList(),
            )
          else
            IntrinsicHeight(
              child: Row(
                children: cards.map((d) => Expanded(
                  child: Padding(
                    padding: EdgeInsets.only(
                        right: d.key == 'academic' ? 0 : 10),
                    child: SizedBox(
                      height: double.infinity,
                      child: PresetCard(
                        icon: d.icon, title: d.title,
                        subtitle: d.subtitle, color: d.color,
                        selected: _preset == d.key,
                        onTap: () => _apply(d.key),
                      ),
                    ),
                  ),
                )).toList(),
              ),
            ),
          const SizedBox(height: 24),
          Row(children: [
            AriaGhostButton(
                label: 'Back', icon: Icons.arrow_back, onPressed: widget.onBack),
            const SizedBox(width: 10),
            Expanded(child: AriaPrimaryButton(
              label: 'Continue',
              icon: Icons.arrow_forward,
              onPressed: widget.onNext,
            )),
          ]),
        ],
      ),
    );
  }
}

class _PresetDef {
  const _PresetDef({
    required this.key, required this.icon,
    required this.title, required this.subtitle, required this.color,
  });
  final String   key, title, subtitle;
  final IconData icon;
  final Color    color;
}

// ─────────────────────────────────────────────────────────────
// Step 3: AI Model (optional)
// ─────────────────────────────────────────────────────────────

class _ModelStep extends StatefulWidget {
  const _ModelStep({super.key, required this.onBack});
  final VoidCallback onBack;

  @override
  State<_ModelStep> createState() => _ModelStepState();
}

class _ModelStepState extends State<_ModelStep> {
  final _keyCtrl   = TextEditingController();
  bool  _detecting = false;
  bool  _launching = false;
  String? _detectedProvider;
  String? _error;

  @override
  void dispose() { _keyCtrl.dispose(); super.dispose(); }

  Future<void> _detect() async {
    final key = _keyCtrl.text.trim();
    if (key.isEmpty) return;
    setState(() { _detecting = true; _error = null; _detectedProvider = null; });
    try {
      final c = context.read<AriaController>();
      c.updatePendingApiKey(key);
      await c.detectProvider();
      if (!mounted) return;
      final providers = c.cloudProviders;
      if (providers.isNotEmpty) {
        final last = providers.last;
        setState(() =>
          _detectedProvider = '${last.detectedName} (${last.detectedProvider})');
      } else {
        setState(() => _error = 'Could not detect provider — check key format.');
      }
    } catch (e) {
      if (mounted) setState(() => _error = 'Detection failed: $e');
    } finally {
      if (mounted) setState(() => _detecting = false);
    }
  }

  Future<void> _launch() async {
    setState(() { _launching = true; _error = null; });
    try {
      final c = context.read<AriaController>();
      await c.startRun();
      if (!mounted) return;
      Navigator.of(context).pushReplacementNamed('/home');
    } catch (e) {
      if (mounted) {
        setState(() { _launching = false; _error = 'Failed to start: $e'; });
      }
    }
  }

  void _skip() => Navigator.of(context).pushReplacementNamed('/home');

  @override
  Widget build(BuildContext context) {
    return _StepWrapper(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Add an AI model', style: AriaTheme.display(size: 26)),
          const SizedBox(height: 6),
          Text('Optional — used for intelligent document cleaning and analysis.',
            style: AriaTheme.inter(size: 14, color: AriaTheme.textMuted)),
          const SizedBox(height: 28),
          AriaInputField(
            controller: _keyCtrl,
            hint: 'sk-...  or  claude-...  or  any provider key',
            label: 'API Key',
            icon: Icons.key_outlined,
            onChanged: (v) {
              if (_detectedProvider != null) {
                setState(() => _detectedProvider = null);
              }
            },
          ),
          const SizedBox(height: 10),
          Row(children: [
            _detecting
              ? Row(mainAxisSize: MainAxisSize.min, children: [
                  const SizedBox(width: 12, height: 12,
                    child: CircularProgressIndicator(
                        strokeWidth: 1.5, color: AriaTheme.textMuted)),
                  const SizedBox(width: 8),
                  Text('Detecting...', style: AriaTheme.inter(size: 13, color: AriaTheme.textMuted)),
                ])
              : AriaGhostButton(
                  label: 'Detect provider',
                  icon: Icons.auto_awesome,
                  onPressed: _detect,
                ),
            const SizedBox(width: 10),
            if (_detectedProvider != null)
              AriaPill(
                  label: _detectedProvider!, color: AriaTheme.statusEmerald),
          ]),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!,
                style: AriaTheme.inter(size: 12, color: AriaTheme.statusRed)),
          ],
          const SizedBox(height: 28),
          SizedBox(
            width: double.infinity,
            child: AriaPrimaryButton(
              label: 'Start Research',
              icon: Icons.rocket_launch_outlined,
              loading: _launching,
              onPressed: _launching ? null : _launch,
            ),
          ),
          const SizedBox(height: 10),
          Row(children: [
            AriaGhostButton(
                label: 'Back', icon: Icons.arrow_back, onPressed: widget.onBack),
            const Spacer(),
            AriaGhostButton(
                label: 'Skip for now', onPressed: _skip),
          ]),
        ],
      ),
    );
  }
}
