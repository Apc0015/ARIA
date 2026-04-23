// ARIA Studio — Dashboard Page
// "Deep Space Research Terminal" — full 3D redesign
// All logic preserved; only the visual layer is redesigned.

import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import '../state/aria_controller.dart';
import '../theme/aria_theme.dart';
import '../widgets/effects_3d.dart';
import '../widgets/neural_widgets.dart';
import '../widgets/shared.dart';

// ─────────────────────────────────────────────────────────────
// Page root
// ─────────────────────────────────────────────────────────────

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});
  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage>
    with TickerProviderStateMixin {

  late final AnimationController _entranceCtrl;
  late final Animation<double>   _entranceFade;
  late final Animation<Offset>   _entranceSlide;

  final _scrollCtrl = ScrollController();
  bool _logExpanded = false;

  @override
  void initState() {
    super.initState();
    _entranceCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 520));
    _entranceFade  = CurvedAnimation(parent: _entranceCtrl, curve: Curves.easeOut);
    _entranceSlide = Tween<Offset>(
      begin: const Offset(0, 0.02), end: Offset.zero,
    ).animate(CurvedAnimation(parent: _entranceCtrl, curve: Curves.easeOut));
    _entranceCtrl.forward();
  }

  @override
  void dispose() {
    _entranceCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  void _scrollToResults() {
    Future.delayed(const Duration(milliseconds: 300), () {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 600),
          curve: Curves.easeInOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AriaTheme.bg0,
      floatingActionButton: MediaQuery.sizeOf(context).width < AriaTheme.mobileMax
          ? FloatingActionButton.small(
              backgroundColor: AriaTheme.brandIndigo.withAlpha(220),
              onPressed: () => showModalBottomSheet(
                context: context,
                backgroundColor: AriaTheme.bg1,
                shape: const RoundedRectangleBorder(
                  borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
                  side: BorderSide(color: AriaTheme.borderStandard),
                ),
                isScrollControlled: true,
                builder: (sheetCtx) => ChangeNotifierProvider.value(
                  value: context.read<AriaController>(),
                  child: SizedBox(
                    height: MediaQuery.sizeOf(sheetCtx).height * 0.65,
                    child: _Sidebar3d(),
                  ),
                ),
              ),
              child: const Icon(Icons.tune, size: 18, color: Colors.white),
            )
          : null,
      body: Stack(children: [
        // [0] Full-screen star field — behind everything
        const Positioned.fill(child: Aria3dStarField()),

        // [1] Ambient floating orbs for deep-space atmosphere
        const Aria3dFloatingOrb(
          size: 400, color: AriaTheme.brandIndigo,
          top: -80, left: -100,
        ),
        const Aria3dFloatingOrb(
          size: 300, color: AriaTheme.accentViolet,
          bottom: -60, right: -80,
        ),

        // [2] Main UI — entrance fade + slide
        Positioned.fill(
          child: FadeTransition(
            opacity: _entranceFade,
            child: SlideTransition(
              position: _entranceSlide,
              child: Column(children: [
                _TopBar3d(),
                Expanded(
                  child: LayoutBuilder(builder: (ctx, constraints) {
                    if (constraints.maxWidth >= AriaTheme.tabletMax) {
                      // Desktop: 220px sidebar
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SizedBox(width: 220, child: _Sidebar3d()),
                          Container(width: 1, color: AriaTheme.borderSubtle),
                          Expanded(
                            child: _MainContent3d(
                              scrollCtrl: _scrollCtrl,
                              logExpanded: _logExpanded,
                              onToggleLog: () =>
                                  setState(() => _logExpanded = !_logExpanded),
                              onRunStarted: _scrollToResults,
                            ),
                          ),
                        ],
                      );
                    } else if (constraints.maxWidth >= AriaTheme.mobileMax) {
                      // Tablet: 160px sidebar
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SizedBox(width: 160, child: _Sidebar3d()),
                          Container(width: 1, color: AriaTheme.borderSubtle),
                          Expanded(
                            child: _MainContent3d(
                              scrollCtrl: _scrollCtrl,
                              logExpanded: _logExpanded,
                              onToggleLog: () =>
                                  setState(() => _logExpanded = !_logExpanded),
                              onRunStarted: _scrollToResults,
                            ),
                          ),
                        ],
                      );
                    }
                    // Mobile: no sidebar
                    return _MainContent3d(
                      scrollCtrl: _scrollCtrl,
                      logExpanded: _logExpanded,
                      onToggleLog: () =>
                          setState(() => _logExpanded = !_logExpanded),
                      onRunStarted: _scrollToResults,
                    );
                  }),
                ),
              ]),
            ),
          ),
        ),
      ]),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Top bar — glass, semi-transparent
// ─────────────────────────────────────────────────────────────

class _TopBar3d extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final c = context.watch<AriaController>();
    return Container(
      height: 52,
      decoration: const BoxDecoration(
        color: Color(0x80080A0F),
        border: Border(bottom: BorderSide(color: AriaTheme.borderSubtle)),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Row(children: [
          // ARIA wordmark
          Text('ARIA',
            style: AriaTheme.display(
              size: 17, color: AriaTheme.brandIndigo, letterSpacing: 2.0)),
          Text(' Studio',
            style: AriaTheme.inter(size: 13, color: AriaTheme.textMuted, letterSpacing: 0.1)),
          const SizedBox(width: 12),
          const _VersionBadge3d(),
          const Spacer(),

          // Active run indicator
          if (c.isBusy || c.runStatus == 'running') ...[
            Row(mainAxisSize: MainAxisSize.min, children: [
              AriaPulseDot(color: AriaTheme.accentViolet),
              const SizedBox(width: 6),
              Text(_stageLabel(c.runStage),
                style: AriaTheme.inter(size: 12, color: AriaTheme.accentViolet)),
            ]),
            const SizedBox(width: 16),
          ],

          // Connection badge
          _ConnectionBadge3d(connected: c.isConnected),
          const SizedBox(width: 16),

          // History icon
          _IconBtn3d(
            icon: Icons.history_outlined,
            tooltip: 'Run History',
            onTap: () => Navigator.of(context).pushNamed('/history'),
          ),
          const SizedBox(width: 8),
          // Settings icon
          _IconBtn3d(
            icon: Icons.settings_outlined,
            tooltip: 'Settings',
            onTap: () => Navigator.of(context).pushNamed('/settings'),
          ),
        ]),
      ),
    );
  }

  static String _stageLabel(String stage) {
    switch (stage) {
      case 'collecting': return 'Collecting…';
      case 'cleaning':   return 'Cleaning…';
      case 'ensemble':   return 'Synthesising…';
      case 'graph':      return 'Building graph…';
      case 'queued':     return 'Queued…';
      default:           return 'Running…';
    }
  }
}

class _VersionBadge3d extends StatelessWidget {
  const _VersionBadge3d();
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
        color: AriaTheme.brandIndigo.withAlpha(18),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: AriaTheme.brandIndigo.withAlpha(45)),
      ),
      child: Text('v5.0',
        style: AriaTheme.mono(size: 9, color: AriaTheme.brandIndigo,
          letterSpacing: 0.4)),
    );
  }
}

class _ConnectionBadge3d extends StatelessWidget {
  const _ConnectionBadge3d({required this.connected});
  final bool connected;
  @override
  Widget build(BuildContext context) {
    final color = connected ? AriaTheme.statusEmerald : AriaTheme.textSubtle;
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Container(
        width: 6, height: 6,
        decoration: BoxDecoration(shape: BoxShape.circle, color: color,
          boxShadow: connected
            ? [BoxShadow(color: color.withAlpha(100), blurRadius: 6)]
            : null),
      ),
      const SizedBox(width: 6),
      Text(connected ? 'Connected' : 'Offline',
        style: AriaTheme.inter(size: 12, weight: FontWeight.w500, color: color)),
    ]);
  }
}

class _IconBtn3d extends StatefulWidget {
  const _IconBtn3d({required this.icon, required this.tooltip, required this.onTap});
  final IconData icon;
  final String tooltip;
  final VoidCallback onTap;
  @override
  State<_IconBtn3d> createState() => _IconBtn3dState();
}
class _IconBtn3dState extends State<_IconBtn3d> {
  bool _hover = false;
  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: widget.tooltip,
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        onEnter: (_) => setState(() => _hover = true),
        onExit:  (_) => setState(() => _hover = false),
        child: GestureDetector(
          onTap: widget.onTap,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 120),
            width: 32, height: 32,
            decoration: BoxDecoration(
              color: _hover
                  ? AriaTheme.brandIndigo.withAlpha(20)
                  : Colors.transparent,
              borderRadius: BorderRadius.circular(6),
              border: _hover
                  ? Border.all(color: AriaTheme.brandIndigo.withAlpha(40))
                  : null,
            ),
            child: Icon(widget.icon, size: 16,
              color: _hover ? AriaTheme.accentViolet : AriaTheme.textMuted),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Sidebar — glass panel, depth + sources + quick start
// ─────────────────────────────────────────────────────────────

class _Sidebar3d extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final c = context.watch<AriaController>();
    return Container(
      color: const Color(0x050F1020),
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(12, 18, 12, 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // DEPTH + CITATION section
            _SidebarSectionCard(child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SidebarHeader('Depth'),
                const SizedBox(height: 10),
                _DepthControl3d(controller: c),
                if (c.citationDepth > 0) ...[
                  const SizedBox(height: 10),
                  Row(children: [
                    Expanded(child: Text('Citation Depth',
                      style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle))),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                      decoration: BoxDecoration(
                        color: AriaTheme.accentViolet.withAlpha(20),
                        borderRadius: BorderRadius.circular(4),
                        border: Border.all(color: AriaTheme.accentViolet.withAlpha(50)),
                      ),
                      child: Text('L${c.citationDepth}',
                        style: AriaTheme.inter(size: 10, color: AriaTheme.accentViolet)),
                    ),
                  ]),
                ],
              ],
            )),

            const SizedBox(height: 10),

            // SOURCES section
            _SidebarSectionCard(child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  _SidebarHeader('Sources'),
                  const Spacer(),
                  GestureDetector(
                    onTap: () => Navigator.of(context).pushNamed('/settings'),
                    child: Text('Edit',
                      style: AriaTheme.inter(size: 11, color: AriaTheme.brandIndigo)),
                  ),
                ]),
                const SizedBox(height: 10),
                _SourceNodesViz(controller: c),
              ],
            )),

            const SizedBox(height: 10),

            // DOMAINS section (shown when domains selected)
            if (c.selectedDomains.isNotEmpty || c.selectedCountries.isNotEmpty)
              _SidebarSectionCard(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (c.selectedDomains.isNotEmpty) ...[
                    _SidebarHeader('Domains'),
                    const SizedBox(height: 8),
                    Wrap(spacing: 5, runSpacing: 5, children: c.selectedDomains.map((d) =>
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                        decoration: BoxDecoration(
                          color: AriaTheme.brandIndigo.withAlpha(20),
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: AriaTheme.brandIndigo.withAlpha(50)),
                        ),
                        child: Text(d, style: AriaTheme.inter(size: 10, color: AriaTheme.brandIndigo)),
                      )
                    ).toList()),
                  ],
                  if (c.selectedDomains.isNotEmpty && c.selectedCountries.isNotEmpty)
                    const SizedBox(height: 8),
                  if (c.selectedCountries.isNotEmpty) ...[
                    _SidebarHeader('Countries'),
                    const SizedBox(height: 8),
                    Wrap(spacing: 5, runSpacing: 5, children: c.selectedCountries.take(6).map((country) =>
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                        decoration: BoxDecoration(
                          color: AriaTheme.statusEmerald.withAlpha(15),
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: AriaTheme.statusEmerald.withAlpha(40)),
                        ),
                        child: Text(country, style: AriaTheme.inter(size: 10, color: AriaTheme.statusEmerald)),
                      )
                    ).toList()),
                  ],
                ],
              )),

            if (c.selectedDomains.isNotEmpty || c.selectedCountries.isNotEmpty)
              const SizedBox(height: 10),

            // QUICK START or LAST RUN
            _SidebarSectionCard(child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SidebarHeader(c.runId.isNotEmpty ? 'Last Run' : 'Quick Start'),
                const SizedBox(height: 10),
                if (c.runId.isNotEmpty)
                  _RunStatsTiles3d(controller: c)
                else
                  _QuickStartHints3d(),
              ],
            )),

            const SizedBox(height: 10),

            // Configure sources button
            _ConfigureBtn3d(),
          ],
        ),
      ),
    );
  }
}

class _SidebarSectionCard extends StatelessWidget {
  const _SidebarSectionCard({required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0x08FFFFFF),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AriaTheme.borderSubtle),
      ),
      child: child,
    );
  }
}

class _SidebarHeader extends StatelessWidget {
  const _SidebarHeader(this.text);
  final String text;
  @override
  Widget build(BuildContext context) {
    return Text(text.toUpperCase(),
      style: AriaTheme.inter(size: 9, weight: FontWeight.w600,
        color: AriaTheme.textSubtle, letterSpacing: 0.9));
  }
}

class _DepthControl3d extends StatelessWidget {
  const _DepthControl3d({required this.controller});
  final AriaController controller;

  static const _labels = {
    1: ('Surface',  '~50 docs'),
    2: ('Standard', '~200 docs'),
    3: ('Deep',     '~500 docs'),
    4: ('Thorough', '~1.5K docs'),
    5: ('Maximum',  '~5K+ docs'),
  };

  @override
  Widget build(BuildContext context) {
    final c    = controller;
    final info = _labels[c.depthLevel]!;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Text('L${c.depthLevel}',
          style: AriaTheme.mono(size: 13, weight: FontWeight.w600,
            color: AriaTheme.textPrimary)),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
          decoration: BoxDecoration(
            color: AriaTheme.brandIndigo.withAlpha(20),
            borderRadius: BorderRadius.circular(3),
            border: Border.all(color: AriaTheme.brandIndigo.withAlpha(45)),
          ),
          child: Text(info.$1.toUpperCase(),
            style: AriaTheme.mono(size: 9, color: AriaTheme.brandIndigo,
              letterSpacing: 0.8)),
        ),
      ]),
      Slider(
        value: c.depthLevel.toDouble(),
        min: 1, max: 5, divisions: 4,
        label: 'L${c.depthLevel}',
        onChanged: (v) => c.updateDepthLevel(v.round()),
      ),
      Text(info.$2,
        style: AriaTheme.mono(size: 10, color: AriaTheme.textSubtle)),
    ]);
  }
}

// ignore: unused_element
class _ActiveSourceChips3d extends StatelessWidget {
  const _ActiveSourceChips3d({required this.controller});
  final AriaController controller;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final active = <String>[];
    if (c.srcWeb)          active.add('Web');
    if (c.srcPdf)          active.add('PDF');
    if (c.srcAcademic)     active.add('Academic');
    if (c.srcWikipedia)    active.add('Wikipedia');
    if (c.srcReddit)       active.add('Reddit');
    if (c.srcHackernews)   active.add('HN');
    if (c.srcYoutube)      active.add('YouTube');
    if (c.srcGithub)       active.add('GitHub');
    if (c.srcNews)         active.add('News');
    if (c.srcGovernment)   active.add('.gov');
    if (c.srcMultilingual) active.add('Multi');
    if (c.srcMedium)       active.add('Medium');
    if (c.srcSubstack)     active.add('Substack');
    if (c.srcDevto)        active.add('Dev.to');
    if (c.srcRss)          active.add('RSS');
    if (c.srcStackoverflow)active.add('SO');
    if (c.srcTwitter)      active.add('Twitter');
    if (c.srcLinkedin)     active.add('LinkedIn');
    if (c.srcNotion)       active.add('Notion');
    if (c.srcSlack)        active.add('Slack');
    if (c.srcPodcast)      active.add('Podcast');

    if (active.isEmpty) {
      return Text('No sources selected',
        style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle));
    }

    return Wrap(
      spacing: 5, runSpacing: 5,
      children: active.map((s) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
        decoration: BoxDecoration(
          color: AriaTheme.statusEmerald.withAlpha(15),
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: AriaTheme.statusEmerald.withAlpha(40)),
        ),
        child: Text(s,
          style: AriaTheme.inter(size: 10, color: AriaTheme.statusEmerald)),
      )).toList(),
    );
  }
}

class _SourceNodesViz extends StatelessWidget {
  const _SourceNodesViz({required this.controller});
  final AriaController controller;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final nodes = [
      (label: 'Web',       color: AriaTheme.glowBlue,      active: c.srcWeb),
      (label: 'PDF',       color: AriaTheme.statusAmber,   active: c.srcPdf),
      (label: 'Academic',  color: AriaTheme.glowPurple,    active: c.srcAcademic),
      (label: 'Wikipedia', color: AriaTheme.glowCyan,      active: c.srcWikipedia),
      (label: 'Reddit',    color: AriaTheme.glowOrange,    active: c.srcReddit),
      (label: 'YouTube',   color: AriaTheme.statusRed,     active: c.srcYoutube),
      (label: 'News',      color: AriaTheme.statusAmber,   active: c.srcNews),
      (label: 'GitHub',    color: AriaTheme.statusEmerald, active: c.srcGithub),
      (label: 'HN',        color: AriaTheme.glowOrange,    active: c.srcHackernews),
    ];
    final active = nodes.where((n) => n.active).toList();

    if (active.isEmpty) {
      return Text('No sources selected',
        style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle));
    }

    return Wrap(
      spacing: 12,
      runSpacing: 12,
      children: active.map((n) => GlowNode(
        key: ValueKey(n.label),
        color: n.color,
        label: n.label,
        active: c.isBusy,
        size: 32,
      )).toList(),
    );
  }
}

class _RunStatsTiles3d extends StatelessWidget {
  const _RunStatsTiles3d({required this.controller});
  final AriaController controller;
  @override
  Widget build(BuildContext context) {
    final c      = controller;
    final docs    = (c.stats['total_collected'] as num? ?? c.documents.length).toString();
    final cleaned = (c.stats['total_cleaned']   as num? ?? 0).toString();
    final sources = (c.stats['sources_hit']     as num? ?? 0).toString();
    return Column(children: [
      _SidebarStatRow(label: 'Documents', value: docs),
      const SizedBox(height: 6),
      _SidebarStatRow(label: 'Cleaned',   value: cleaned),
      const SizedBox(height: 6),
      _SidebarStatRow(label: 'Sources',   value: sources),
      if (c.gapsCount > 0) ...[
        const SizedBox(height: 6),
        _SidebarStatRow(label: 'Gaps', value: c.gapsCount.toString(),
          accent: AriaTheme.statusAmber),
      ],
    ]);
  }
}

class _SidebarStatRow extends StatelessWidget {
  const _SidebarStatRow({required this.label, required this.value, this.accent});
  final String label, value;
  final Color? accent;
  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Expanded(child: Text(label,
        style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle))),
      Text(value, style: AriaTheme.mono(
        size: 12, weight: FontWeight.w500,
        color: accent ?? AriaTheme.textPrimary)),
    ]);
  }
}

class _QuickStartHints3d extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    const hints = [
      'Enter your research topic',
      'Optionally add a focus angle',
      'Hit Launch Run to begin',
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: hints.asMap().entries.map((e) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(
            width: 16, height: 16,
            margin: const EdgeInsets.only(top: 1),
            decoration: BoxDecoration(
              color: AriaTheme.brandIndigo.withAlpha(20),
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: AriaTheme.brandIndigo.withAlpha(50)),
            ),
            child: Center(child: Text('${e.key + 1}',
              style: AriaTheme.inter(size: 9, weight: FontWeight.w500,
                color: AriaTheme.brandIndigo))),
          ),
          const SizedBox(width: 8),
          Expanded(child: Text(e.value,
            style: AriaTheme.inter(size: 11, color: AriaTheme.textMuted))),
        ]),
      )).toList(),
    );
  }
}

class _ConfigureBtn3d extends StatefulWidget {
  @override
  State<_ConfigureBtn3d> createState() => _ConfigureBtn3dState();
}
class _ConfigureBtn3dState extends State<_ConfigureBtn3d> {
  bool _hover = false;
  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit:  (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: () => Navigator.of(context).pushNamed('/settings'),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
          decoration: BoxDecoration(
            color: _hover
                ? AriaTheme.brandIndigo.withAlpha(20)
                : const Color(0x08FFFFFF),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: _hover
                  ? AriaTheme.brandIndigo.withAlpha(60)
                  : AriaTheme.borderSubtle),
            boxShadow: _hover
                ? [BoxShadow(color: AriaTheme.brandIndigo.withAlpha(20),
                    blurRadius: 12)]
                : null,
          ),
          child: Row(children: [
            Icon(Icons.settings_outlined, size: 13,
              color: _hover ? AriaTheme.accentViolet : AriaTheme.textMuted),
            const SizedBox(width: 8),
            Expanded(child: Text('Configure Sources →',
              style: AriaTheme.inter(size: 11,
                color: _hover ? AriaTheme.accentViolet : AriaTheme.textMuted))),
          ]),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Main content area
// ─────────────────────────────────────────────────────────────

class _MainContent3d extends StatelessWidget {
  const _MainContent3d({
    required this.scrollCtrl,
    required this.logExpanded,
    required this.onToggleLog,
    required this.onRunStarted,
  });
  final ScrollController scrollCtrl;
  final bool logExpanded;
  final VoidCallback onToggleLog;
  final VoidCallback onRunStarted;

  @override
  Widget build(BuildContext context) {
    final c = context.watch<AriaController>();
    final isRunning  = c.isBusy || c.runStatus == 'running';
    final isDone     = c.runStatus == 'completed';
    final hasResults = c.documents.isNotEmpty || c.ensembleDocuments.isNotEmpty;
    final isEmpty    = c.runId.isEmpty && !c.isBusy;

    return Column(children: [
      // Command bar
      _CommandBar3d(onRunStarted: onRunStarted),

      // Connected strip
      if (c.isConnected && !isRunning && isEmpty)
        _ConnectedStrip3d(),

      // Stage progress while running
      if (isRunning)
        _StageProgress3d(stage: c.runStage, message: c.runMessage),

      // Metrics row when done
      if (isDone && hasResults) ...[
        _MetricsRow3d(controller: c),
      ],

      // Content area
      Expanded(
        child: CustomScrollView(
          controller: scrollCtrl,
          slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
              sliver: SliverToBoxAdapter(
                child: isEmpty
                    ? _EmptyState3d()
                    : isRunning && !hasResults
                        ? _RunningState3d()
                        : _RunOutputArea3d(
                            logExpanded: logExpanded,
                            onToggleLog: onToggleLog,
                          ),
              ),
            ),
            const SliverPadding(padding: EdgeInsets.only(bottom: 48)),
          ],
        ),
      ),
    ]);
  }
}

// ─────────────────────────────────────────────────────────────
// Command bar — glass panel with query + angle + launch
// ─────────────────────────────────────────────────────────────

class _CommandBar3d extends StatefulWidget {
  const _CommandBar3d({required this.onRunStarted});
  final VoidCallback onRunStarted;
  @override
  State<_CommandBar3d> createState() => _CommandBar3dState();
}

class _CommandBar3dState extends State<_CommandBar3d>
    with SingleTickerProviderStateMixin {
  late final TextEditingController _topicCtrl;
  late final TextEditingController _intentCtrl;
  late final AnimationController   _placeholderCtrl;
  int    _placeholderIdx = 0;
  Timer? _placeholderTimer;

  static const _placeholders = [
    'AI policy in US county governments…',
    'Climate adaptation in coastal cities…',
    'Quantum computing applications in logistics…',
    'Mental health treatment outcomes 2020–2024…',
    'Emerging battery technologies for EVs…',
    'Supply chain resilience post-pandemic…',
  ];

  @override
  void initState() {
    super.initState();
    final c = context.read<AriaController>();
    _topicCtrl  = TextEditingController(text: c.topic);
    _intentCtrl = TextEditingController(text: c.intent);
    _placeholderCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 400));
    _placeholderCtrl.value = 1.0;
    _startPlaceholderCycle();
  }

  void _startPlaceholderCycle() {
    _placeholderTimer = Timer.periodic(const Duration(seconds: 4), (_) {
      if (!mounted) return;
      final c = context.read<AriaController>();
      if (c.topic.isNotEmpty) return;
      _placeholderCtrl.reverse().then((_) {
        if (!mounted) return;
        setState(() => _placeholderIdx = (_placeholderIdx + 1) % _placeholders.length);
        _placeholderCtrl.forward();
      });
    });
  }

  @override
  void dispose() {
    _placeholderTimer?.cancel();
    _placeholderCtrl.dispose();
    _topicCtrl.dispose();
    _intentCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c       = context.watch<AriaController>();
    final blocked = c.blockedAuthSources;
    final canRun  = !c.isBusy && c.isConnected
        && c.topic.trim().isNotEmpty && blocked.isEmpty;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 14, 16, 10),
      child: Aria3dGlassPanel(
        glowColor: c.topic.isNotEmpty ? AriaTheme.brandIndigo : Colors.transparent,
        borderRadius: 10,
        padding: EdgeInsets.zero,
        child: Column(mainAxisSize: MainAxisSize.min, children: [

          // ── Top accent rule — activates when topic is non-empty ──
          AnimatedContainer(
            duration: AriaTheme.durNormal,
            height: 2,
            decoration: BoxDecoration(
              gradient: LinearGradient(colors: [
                c.topic.isNotEmpty ? AriaTheme.brandIndigo : Colors.transparent,
                c.topic.isNotEmpty ? AriaTheme.accentViolet : Colors.transparent,
                c.topic.isNotEmpty ? AriaTheme.brandIndigo.withAlpha(0) : Colors.transparent,
              ]),
            ),
          ),

          // ── Query label + shortcut hint ──
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 8, 14, 0),
            child: Row(children: [
              Text('RESEARCH QUERY',
                style: AriaTheme.mono(size: 9, color: AriaTheme.textSubtle,
                  letterSpacing: 1.4, height: 1)),
              const Spacer(),
              if (!c.isBusy && !AriaTheme.isMobile(context))
                Text('⌘ ↵  to launch',
                  style: AriaTheme.mono(size: 9,
                    color: AriaTheme.textSubtle.withAlpha(80), letterSpacing: 0.5, height: 1)),
            ]),
          ),
          const SizedBox(height: 4),

          // ── Topic row ──
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 2, 10, 4),
            child: Row(children: [
              AnimatedSwitcher(
                duration: AriaTheme.durFast,
                child: c.topic.isNotEmpty
                    ? Icon(Icons.circle, size: 7, key: const ValueKey('filled'),
                        color: AriaTheme.brandIndigo)
                    : Icon(Icons.search, size: 17, key: const ValueKey('search'),
                        color: AriaTheme.textSubtle),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: TextField(
                  controller: _topicCtrl,
                  onChanged: c.updateTopic,
                  style: AriaTheme.inter(size: 16, color: AriaTheme.textPrimary,
                    letterSpacing: -0.2),
                  decoration: InputDecoration(
                    hintText: _placeholders[_placeholderIdx],
                    hintStyle: AriaTheme.inter(size: 16, color: AriaTheme.textSubtle),
                    border: InputBorder.none,
                    enabledBorder: InputBorder.none,
                    focusedBorder: InputBorder.none,
                    isDense: true,
                    contentPadding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Aria3dButton(
                label: 'Launch Run',
                icon: Icons.rocket_launch_outlined,
                loading: c.isBusy,
                enabled: canRun,
                onTap: () async {
                  if (!canRun) return;
                  await c.startRun();
                  widget.onRunStarted();
                },
              ),
            ]),
          ),

          // Divider
          Container(height: 1, color: AriaTheme.borderSubtle),

          // ── Focus row ──
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 0, 14, 0),
            child: Row(children: [
              Text('FOCUS',
                style: AriaTheme.mono(size: 9, color: AriaTheme.textSubtle.withAlpha(80),
                  letterSpacing: 1.2, height: 1)),
              const SizedBox(width: 10),
              Expanded(
                child: TextField(
                  controller: _intentCtrl,
                  onChanged: c.updateIntent,
                  style: AriaTheme.inter(size: 13, color: AriaTheme.textSecondary),
                  decoration: InputDecoration(
                    hintText: 'Specific angle or question (optional)…',
                    hintStyle: AriaTheme.inter(size: 13, color: AriaTheme.textSubtle),
                    border: InputBorder.none,
                    enabledBorder: InputBorder.none,
                    focusedBorder: InputBorder.none,
                    isDense: true,
                    contentPadding: const EdgeInsets.symmetric(vertical: 10),
                  ),
                ),
              ),
            ]),
          ),

          // ── Controls row ──
          Container(height: 1, color: AriaTheme.borderSubtle),
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 6, 14, 6),
            child: Row(children: [
              // Domain selector
              _Aria5Chip(
                icon: Icons.category_outlined,
                label: c.selectedDomains.isEmpty
                    ? 'Domains'
                    : '${c.selectedDomains.length} domain${c.selectedDomains.length > 1 ? "s" : ""}',
                active: c.selectedDomains.isNotEmpty,
                color: AriaTheme.brandIndigo,
                onTap: () => _showDomainSheet(context, c),
              ),
              const SizedBox(width: 6),
              // Country selector
              _Aria5Chip(
                icon: Icons.public_outlined,
                label: c.selectedCountries.isEmpty
                    ? 'Countries'
                    : '${c.selectedCountries.length} countr${c.selectedCountries.length > 1 ? "ies" : "y"}',
                active: c.selectedCountries.isNotEmpty,
                color: AriaTheme.statusEmerald,
                onTap: () => _showCountrySheet(context, c),
              ),
              const SizedBox(width: 6),
              // Citation depth
              _Aria5Chip(
                icon: Icons.account_tree_outlined,
                label: c.citationDepth == 0 ? 'Citations off' : 'Citations L${c.citationDepth}',
                active: c.citationDepth > 0,
                color: AriaTheme.accentViolet,
                onTap: () => _cycleCitationDepth(c),
              ),
              const Spacer(),
              // AI Assist button
              if (c.topic.isNotEmpty)
                GestureDetector(
                  onTap: c.isAnalyzingIntent ? null : () => c.runIntentAnalysis(),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 150),
                    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                    decoration: BoxDecoration(
                      color: AriaTheme.accentViolet.withAlpha(15),
                      borderRadius: BorderRadius.circular(5),
                      border: Border.all(color: AriaTheme.accentViolet.withAlpha(40)),
                    ),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      c.isAnalyzingIntent
                          ? const SizedBox(width: 10, height: 10,
                              child: CircularProgressIndicator(strokeWidth: 1.5,
                                  color: AriaTheme.accentViolet))
                          : const Icon(Icons.auto_awesome, size: 11, color: AriaTheme.accentViolet),
                      const SizedBox(width: 5),
                      Text('AI Assist',
                          style: AriaTheme.inter(size: 11, color: AriaTheme.accentViolet)),
                    ]),
                  ),
                ),
            ]),
          ),
          // ── Validation strip ──
          if (blocked.isNotEmpty || c.lastValidationMessage.isNotEmpty)
            _ValidationStrip3d(blocked: blocked, message: c.lastValidationMessage),
        ]),
      ),
    );
  }

  void _cycleCitationDepth(AriaController c) {
    c.updateCitationDepth((c.citationDepth + 1) % 4);
  }

  void _showDomainSheet(BuildContext context, AriaController c) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AriaTheme.bg1,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(12)),
        side: BorderSide(color: AriaTheme.borderStandard),
      ),
      builder: (ctx) => _DomainSheet(controller: c),
    );
  }

  void _showCountrySheet(BuildContext context, AriaController c) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AriaTheme.bg1,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(12)),
        side: BorderSide(color: AriaTheme.borderStandard),
      ),
      builder: (ctx) => _CountrySheet(controller: c),
    );
  }
}

class _ValidationStrip3d extends StatelessWidget {
  const _ValidationStrip3d({required this.blocked, required this.message});
  final List<String> blocked;
  final String message;
  @override
  Widget build(BuildContext context) {
    final isWarning = blocked.isNotEmpty;
    final text = isWarning
        ? 'Connect required: ${blocked.join(", ")}'
        : message;
    final color = isWarning ? AriaTheme.statusAmber : AriaTheme.textSubtle;
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 8, 14, 10),
      child: Row(children: [
        Icon(isWarning ? Icons.warning_amber_outlined : Icons.info_outline,
          size: 13, color: color),
        const SizedBox(width: 6),
        Flexible(child: Text(text,
          style: AriaTheme.inter(size: 11, color: color))),
      ]),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Connected strip
// ─────────────────────────────────────────────────────────────

class _ConnectedStrip3d extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      child: Row(children: [
        Container(width: 4, height: 4,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: AriaTheme.statusEmerald,
            boxShadow: [BoxShadow(color: AriaTheme.statusEmerald.withAlpha(100),
              blurRadius: 5)],
          )),
        const SizedBox(width: 8),
        Text('CONNECTED',
          style: AriaTheme.mono(size: 9, color: AriaTheme.statusEmerald,
            letterSpacing: 1.3, height: 1)),
        const SizedBox(width: 10),
        Container(width: 1, height: 10, color: AriaTheme.borderSubtle),
        const SizedBox(width: 10),
        Text('System ready for research',
          style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
      ]),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Stage progress strip
// ─────────────────────────────────────────────────────────────

class _StageProgress3d extends StatelessWidget {
  const _StageProgress3d({required this.stage, required this.message});
  final String stage, message;

  static const _stages = [
    'queued', 'collecting', 'cleaning', 'ensemble', 'graph', 'finalizing',
  ];

  static const _stageLabels = {
    'queued':     'Queue',
    'collecting': 'Collect',
    'cleaning':   'Clean',
    'ensemble':   'Synth',
    'graph':      'Graph',
    'finalizing': 'Final',
  };

  @override
  Widget build(BuildContext context) {
    final idx = _stages.indexOf(stage).clamp(0, _stages.length - 1);
    final pct = (idx + 1) / _stages.length;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
      decoration: BoxDecoration(
        color: AriaTheme.accentViolet.withAlpha(8),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AriaTheme.accentViolet.withAlpha(30)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          AriaPulseDot(color: AriaTheme.accentViolet),
          const SizedBox(width: 8),
          Flexible(child: Text(
            message.isNotEmpty ? message : 'Processing…',
            style: AriaTheme.inter(size: 12, color: AriaTheme.textSecondary))),
        ]),
        const SizedBox(height: 8),
        Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
          // Orbital progress ring
          SizedBox(
            width: 48, height: 48,
            child: CustomPaint(
              painter: _OrbitalProgressPainter(
                progress: pct,
                color: AriaTheme.accentViolet,
              ),
              child: Center(
                child: Text('${(pct * 100).round()}%',
                  style: AriaTheme.mono(size: 9, color: AriaTheme.accentViolet)),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(2),
                child: LinearProgressIndicator(
                  value: pct,
                  backgroundColor: AriaTheme.bg3,
                  valueColor: const AlwaysStoppedAnimation(AriaTheme.accentViolet),
                  minHeight: 2,
                ),
              ),
              const SizedBox(height: 8),
              Row(
                children: _stages.asMap().entries.map((e) {
                  final active = e.key == idx;
                  final done   = e.key < idx;
                  final col = active ? AriaTheme.accentViolet
                      : done ? AriaTheme.statusEmerald
                      : AriaTheme.textSubtle;
                  return Expanded(child: Padding(
                    padding: const EdgeInsets.only(right: 4),
                    child: Text(_stageLabels[e.value] ?? e.value,
                      style: AriaTheme.mono(size: 8, color: col, letterSpacing: 0),
                      overflow: TextOverflow.ellipsis),
                  ));
                }).toList(),
              ),
            ],
          )),
        ]),
      ]),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Orbital progress ring painter
// ─────────────────────────────────────────────────────────────

class _OrbitalProgressPainter extends CustomPainter {
  const _OrbitalProgressPainter({required this.progress, required this.color});
  final double progress;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 3;
    final bgPaint = Paint()
      ..color = color.withAlpha(25)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5;
    canvas.drawCircle(center, radius, bgPaint);
    final arcPaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2);
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2,
      progress * 2 * math.pi,
      false,
      arcPaint,
    );
  }

  @override
  bool shouldRepaint(_OrbitalProgressPainter old) =>
      old.progress != progress || old.color != color;
}

// ─────────────────────────────────────────────────────────────
// Metrics row — Aria3dMetricTile row
// ─────────────────────────────────────────────────────────────

class _MetricsRow3d extends StatelessWidget {
  const _MetricsRow3d({required this.controller});
  final AriaController controller;

  @override
  Widget build(BuildContext context) {
    final c        = controller;
    final docs      = (c.stats['total_collected'] as num? ?? c.documents.length);
    final cleaned   = (c.stats['total_cleaned']   as num? ?? 0);
    final srcHit    = (c.stats['sources_hit']      as num? ?? 0);
    final ensemble  = c.ensembleDocuments.length;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
      child: Row(children: [
        Expanded(child: Aria3dMetricTile(
          label: 'Collected',
          value: docs.toString(),
          icon: Icons.article_outlined,
          accent: AriaTheme.textMuted,
        )),
        const SizedBox(width: 8),
        Expanded(child: Aria3dMetricTile(
          label: 'Cleaned',
          value: cleaned.toString(),
          icon: Icons.check_circle_outline,
          accent: cleaned > 0 ? AriaTheme.statusEmerald : AriaTheme.textSubtle,
        )),
        const SizedBox(width: 8),
        Expanded(child: Aria3dMetricTile(
          label: 'Sources Hit',
          value: srcHit.toString(),
          icon: Icons.cloud_download_outlined,
          accent: srcHit > 0 ? AriaTheme.brandIndigo : AriaTheme.textSubtle,
        )),
        const SizedBox(width: 8),
        Expanded(child: Aria3dMetricTile(
          label: 'Answers',
          value: ensemble.toString(),
          icon: Icons.psychology_outlined,
          accent: ensemble > 0 ? AriaTheme.accentViolet : AriaTheme.textSubtle,
        )),
      ]),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Empty state — solar system of orbiting data sources
// ─────────────────────────────────────────────────────────────

class _EmptyState3d extends StatefulWidget {
  @override
  State<_EmptyState3d> createState() => _EmptyState3dState();
}

class _EmptyState3dState extends State<_EmptyState3d>
    with TickerProviderStateMixin {
  late final AnimationController _orbitCtrl;
  late final AnimationController _orbitSlowCtrl;

  @override
  void initState() {
    super.initState();
    _orbitCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 14))
      ..repeat();
    _orbitSlowCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 22))
      ..repeat();
  }

  @override
  void dispose() {
    _orbitCtrl.dispose();
    _orbitSlowCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      mainAxisSize: MainAxisSize.min,
      children: [
        const SizedBox(height: 20),
        SizedBox(
          height: 340,
            child: Stack(alignment: Alignment.center, clipBehavior: Clip.none, children: [
              // Background grid
              const Positioned.fill(child: Aria3dGrid()),

              // Orbit rings (ellipses painted)
              CustomPaint(
                size: const Size(340, 340),
                painter: _OrbitRingsPainter(),
              ),

              // Inner orbit — source icons (fast)
              AnimatedBuilder(
                animation: _orbitCtrl,
                builder: (_, child) => Stack(children: [
                  _OrbitIcon(
                    angle: _orbitCtrl.value * 2 * math.pi,
                    radius: 90, flatness: 0.38,
                    icon: Icons.language, color: AriaTheme.brandIndigo,
                    label: 'Web',
                  ),
                  _OrbitIcon(
                    angle: _orbitCtrl.value * 2 * math.pi + math.pi,
                    radius: 90, flatness: 0.38,
                    icon: Icons.picture_as_pdf_outlined, color: AriaTheme.statusAmber,
                    label: 'PDF',
                  ),
                  _OrbitIcon(
                    angle: _orbitCtrl.value * 2 * math.pi + math.pi / 2,
                    radius: 90, flatness: 0.38,
                    icon: Icons.school_outlined, color: AriaTheme.accentViolet,
                    label: 'Academic',
                  ),
                ]),
              ),

              // Outer orbit — more sources (slow)
              AnimatedBuilder(
                animation: _orbitSlowCtrl,
                builder: (_, child) => Stack(children: [
                  _OrbitIcon(
                    angle: _orbitSlowCtrl.value * 2 * math.pi,
                    radius: 150, flatness: 0.32,
                    icon: Icons.code, color: AriaTheme.statusEmerald,
                    label: 'Code',
                  ),
                  _OrbitIcon(
                    angle: _orbitSlowCtrl.value * 2 * math.pi + math.pi * 2 / 3,
                    radius: 150, flatness: 0.32,
                    icon: Icons.newspaper_outlined, color: AriaTheme.statusAmber,
                    label: 'News',
                  ),
                  _OrbitIcon(
                    angle: _orbitSlowCtrl.value * 2 * math.pi + math.pi * 4 / 3,
                    radius: 150, flatness: 0.32,
                    icon: Icons.hub_outlined, color: AriaTheme.brandIndigo,
                    label: 'Graph',
                  ),
                ]),
              ),

              // Center orb
              const Aria3dOrb(size: 130, color: AriaTheme.brandIndigo),
            ]),
          ),

          const SizedBox(height: 32),

          // Headline
          Text('Start a research run',
            style: AriaTheme.display(size: 26, color: AriaTheme.textPrimary)),
          const SizedBox(height: 10),
          Text(
            'Enter a topic, choose your sources in the sidebar,\nthen hit Launch Run.',
            style: AriaTheme.inter(size: 14, color: AriaTheme.textSubtle),
            textAlign: TextAlign.center,
          ),

          const SizedBox(height: 24),

          // Capability chips
          Wrap(
            spacing: 8, runSpacing: 8,
            alignment: WrapAlignment.center,
            children: const [
              _CapPill3d(icon: Icons.document_scanner_outlined, label: '37+ Sources'),
              _CapPill3d(icon: Icons.category_outlined,         label: '12 Domains'),
              _CapPill3d(icon: Icons.public_outlined,           label: '44 Countries'),
              _CapPill3d(icon: Icons.account_tree_outlined,     label: 'Citation Intel'),
              _CapPill3d(icon: Icons.psychology_outlined,       label: 'AI Ensemble'),
              _CapPill3d(icon: Icons.hub_outlined,              label: 'Knowledge Graph'),
              _CapPill3d(icon: Icons.manage_search,             label: 'Gap Analysis'),
              _CapPill3d(icon: Icons.translate,                 label: 'Multilingual'),
            ],
          ),
        ],
      );
  }
}

class _OrbitRingsPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;

    for (final pair in [
      (90.0, 0.38),
      (150.0, 0.32),
    ]) {
      final r   = pair.$1;
      final flat = pair.$2;
      final paint = Paint()
        ..color = AriaTheme.brandIndigo.withAlpha(22)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 0.8;
      canvas.drawOval(
        Rect.fromCenter(center: Offset(cx, cy),
          width: r * 2, height: r * 2 * flat),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _OrbitRingsPainter old) => false;
}

class _OrbitIcon extends StatelessWidget {
  const _OrbitIcon({
    required this.angle,
    required this.radius,
    required this.flatness,
    required this.icon,
    required this.color,
    required this.label,
  });
  final double  angle, radius, flatness;
  final IconData icon;
  final Color   color;
  final String  label;

  @override
  Widget build(BuildContext context) {
    final x = math.cos(angle) * radius;
    final y = math.sin(angle) * radius * flatness;
    return Transform.translate(
      offset: Offset(x, y),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Container(
          width: 32, height: 32,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: color.withAlpha(20),
            border: Border.all(color: color.withAlpha(60)),
            boxShadow: [BoxShadow(color: color.withAlpha(40), blurRadius: 10)],
          ),
          child: Icon(icon, size: 16, color: color),
        ),
        const SizedBox(height: 3),
        Text(label,
          style: AriaTheme.inter(size: 9, color: color.withAlpha(200))),
      ]),
    );
  }
}

class _CapPill3d extends StatelessWidget {
  const _CapPill3d({required this.icon, required this.label});
  final IconData icon;
  final String   label;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0x08FFFFFF),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AriaTheme.borderSubtle),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 13, color: AriaTheme.textSubtle),
        const SizedBox(width: 6),
        Text(label, style: AriaTheme.inter(size: 12, color: AriaTheme.textMuted)),
      ]),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Running state — shown while running with no results yet
// ─────────────────────────────────────────────────────────────

class _RunningState3d extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 400,
      child: Center(
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          const Aria3dOrb(size: 100, color: AriaTheme.accentViolet),
          const SizedBox(height: 28),
          Text('Researching…',
            style: AriaTheme.inter(size: 18, weight: FontWeight.w500,
              color: AriaTheme.textPrimary)),
          const SizedBox(height: 8),
          Text('Collecting and processing sources',
            style: AriaTheme.inter(size: 13, color: AriaTheme.textSubtle)),
        ]),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Run output area — staggered result panels
// ─────────────────────────────────────────────────────────────

class _RunOutputArea3d extends StatelessWidget {
  const _RunOutputArea3d({required this.logExpanded, required this.onToggleLog});
  final bool logExpanded;
  final VoidCallback onToggleLog;

  @override
  Widget build(BuildContext context) {
    final c = context.watch<AriaController>();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Run status header
        _RunStatusHeader3d(controller: c),
        const SizedBox(height: 14),

        // Download panel — shown whenever a run exists (completed, failed, or in-flight).
        // Each button handles "file not ready yet" gracefully with its own error state.
        if (c.runId.isNotEmpty && c.runStatus != 'idle' && c.runStatus != 'queued') ...[
          Aria3dStagger(index: 0, child:
            _ResultSection3d(
              icon: Icons.download_outlined,
              title: 'Download Results',
              glowColor: AriaTheme.brandIndigo,
              child: _DownloadContent(controller: c),
            ),
          ),
          const SizedBox(height: 12),
        ],

        // Log toggle
        _LogToggleRow3d(
          logCount: c.logs.length,
          expanded: logExpanded,
          onToggle: onToggleLog,
        ),
        if (logExpanded) ...[
          const SizedBox(height: 8),
          _LogPanel3d(logs: c.logs),
          const SizedBox(height: 16),
        ] else
          const SizedBox(height: 12),

        // Documents
        if (c.documents.isNotEmpty)
          Aria3dStagger(index: 0, child:
            _ResultSection3d(
              icon: Icons.article_outlined,
              title: 'Documents',
              badge: '${c.documents.length}',
              glowColor: AriaTheme.brandIndigo,
              child: _DocumentsContent(controller: c),
            ),
          ),

        // Ensemble answers
        if (c.ensembleDocuments.isNotEmpty) ...[
          const SizedBox(height: 12),
          Aria3dStagger(index: 1, child:
            _ResultSection3d(
              icon: Icons.psychology_outlined,
              title: 'AI Ensemble Answers',
              badge: '${c.ensembleDocuments.length}',
              glowColor: AriaTheme.accentViolet,
              child: _EnsembleContent(controller: c),
            ),
          ),
        ],

        // Knowledge graph
        if (c.knowledgeGraph.isNotEmpty) ...[
          const SizedBox(height: 12),
          Aria3dStagger(index: 2, child:
            _ResultSection3d(
              icon: Icons.hub_outlined,
              title: 'Knowledge Graph',
              badge: '${(c.knowledgeGraph["node_count"] as num? ?? 0).toInt()} nodes',
              glowColor: AriaTheme.statusEmerald,
              child: _KnowledgeGraphContent(controller: c),
            ),
          ),
        ],

        // Gap analysis
        if (c.gapAnalysis['has_gaps'] == true) ...[
          const SizedBox(height: 12),
          Aria3dStagger(index: 3, child:
            _ResultSection3d(
              icon: Icons.manage_search,
              title: 'Research Gaps',
              badge: '${c.gapsCount}',
              glowColor: AriaTheme.statusAmber,
              child: _GapAnalysisContent(controller: c),
            ),
          ),
        ],

        // Image gallery
        if (c.collectedImages.isNotEmpty) ...[
          const SizedBox(height: 12),
          Aria3dStagger(index: 4, child:
            _ResultSection3d(
              icon: Icons.image_outlined,
              title: 'Images',
              badge: '${c.collectedImages.length}',
              glowColor: AriaTheme.statusAmber,
              child: _ImageGalleryContent(controller: c),
            ),
          ),
        ],

        // Methodology (ARIA 5.0) — always shown when run is done
        if (c.runStatus == 'completed') ...[
          const SizedBox(height: 12),
          Aria3dStagger(index: 5, child:
            _ResultSection3d(
              icon: Icons.account_tree_outlined,
              title: 'Collection Methodology',
              glowColor: AriaTheme.textMuted,
              child: _MethodologyContent(controller: c),
            ),
          ),
        ],

      ],
    );
  }
}

// ── Run status header ──

class _RunStatusHeader3d extends StatelessWidget {
  const _RunStatusHeader3d({required this.controller});
  final AriaController controller;

  @override
  Widget build(BuildContext context) {
    final c         = controller;
    final isRunning = c.runStatus == 'running' || c.isBusy;
    final isDone    = c.runStatus == 'completed';
    final isFailed  = c.runStatus == 'failed';

    Color statusColor;
    String statusText;
    if (isRunning) {
      statusColor = AriaTheme.accentViolet;
      statusText  = 'Running';
    } else if (isDone) {
      statusColor = AriaTheme.statusEmerald;
      statusText  = 'Completed';
    } else if (isFailed) {
      statusColor = AriaTheme.statusRed;
      statusText  = 'Failed';
    } else {
      statusColor = AriaTheme.statusAmber;
      statusText  = c.runStatus.isNotEmpty ? c.runStatus : 'Queued';
    }

    return Row(children: [
      if (isRunning)
        AriaPulseDot(color: statusColor)
      else
        Container(width: 6, height: 6,
          decoration: BoxDecoration(shape: BoxShape.circle, color: statusColor,
            boxShadow: [BoxShadow(color: statusColor.withAlpha(80), blurRadius: 6)])),
      const SizedBox(width: 8),
      Text(statusText,
        style: AriaTheme.inter(size: 13, weight: FontWeight.w500, color: statusColor)),
      if (c.topic.isNotEmpty) ...[
        const SizedBox(width: 8),
        Text('—', style: AriaTheme.inter(size: 13, color: AriaTheme.textSubtle)),
        const SizedBox(width: 8),
        Flexible(child: Text(c.topic,
          style: AriaTheme.inter(size: 13, color: AriaTheme.textMuted),
          overflow: TextOverflow.ellipsis)),
      ],
      const Spacer(),
      if (c.runId.isNotEmpty) ...[
        Text(c.runId.substring(0, math.min(8, c.runId.length)).toUpperCase(),
          style: AriaTheme.mono(size: 10, color: AriaTheme.textSubtle, letterSpacing: 0.8)),
        if (isDone) ...[
          const SizedBox(width: 10),
          GestureDetector(
            onTap: () => Navigator.of(context).pushNamed('/reports', arguments: c.runId),
            child: MouseRegion(
              cursor: SystemMouseCursors.click,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AriaTheme.brandIndigo.withAlpha(20),
                  borderRadius: BorderRadius.circular(5),
                  border: Border.all(color: AriaTheme.brandIndigo.withAlpha(60)),
                ),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.bar_chart_outlined, size: 12, color: AriaTheme.brandIndigo),
                  const SizedBox(width: 5),
                  Text('View Report', style: AriaTheme.inter(
                    size: 11, weight: FontWeight.w500, color: AriaTheme.brandIndigo)),
                ]),
              ),
            ),
          ),
        ],
      ],
    ]);
  }
}

// ── Log toggle + panel ──

class _LogToggleRow3d extends StatelessWidget {
  const _LogToggleRow3d({
    required this.logCount,
    required this.expanded,
    required this.onToggle,
  });
  final int logCount;
  final bool expanded;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onToggle,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: const Color(0x08FFFFFF),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: AriaTheme.borderSubtle),
        ),
        child: Row(children: [
          Icon(
            expanded ? Icons.keyboard_arrow_down : Icons.keyboard_arrow_right,
            size: 14, color: AriaTheme.textSubtle),
          const SizedBox(width: 6),
          Text('Activity Log',
            style: AriaTheme.inter(size: 12, weight: FontWeight.w500,
              color: AriaTheme.textMuted)),
          if (logCount > 0) ...[
            const SizedBox(width: 8),
            AriaPill(label: '$logCount', subtle: true),
          ],
        ]),
      ),
    );
  }
}

class _LogPanel3d extends StatefulWidget {
  const _LogPanel3d({required this.logs});
  final List<Map<String, dynamic>> logs;
  @override
  State<_LogPanel3d> createState() => _LogPanel3dState();
}
class _LogPanel3dState extends State<_LogPanel3d> {
  final _scrollCtrl = ScrollController();

  @override
  void didUpdateWidget(_LogPanel3d old) {
    super.didUpdateWidget(old);
    if (widget.logs.length != old.logs.length) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scrollCtrl.hasClients) {
          _scrollCtrl.animateTo(
            _scrollCtrl.position.maxScrollExtent,
            duration: const Duration(milliseconds: 200),
            curve: Curves.easeOut,
          );
        }
      });
    }
  }

  @override
  void dispose() { _scrollCtrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 180,
      decoration: BoxDecoration(
        color: const Color(0x0A080A0F),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AriaTheme.borderSubtle),
      ),
      child: widget.logs.isEmpty
          ? Center(child: Text('Waiting for events…',
              style: AriaTheme.inter(size: 12, color: AriaTheme.textSubtle)))
          : ListView.builder(
              controller: _scrollCtrl,
              padding: const EdgeInsets.all(10),
              itemCount: widget.logs.length,
              itemBuilder: (_, i) {
                final log = widget.logs[i];
                final lvl = log['level'] as String? ?? 'info';
                final msg = log['message'] as String? ?? '';
                final ts  = log['timestamp'] as String? ?? '';
                Color logColor;
                switch (lvl) {
                  case 'error':   logColor = AriaTheme.statusRed;     break;
                  case 'warning': logColor = AriaTheme.statusAmber;   break;
                  case 'success': logColor = AriaTheme.statusEmerald; break;
                  default:        logColor = AriaTheme.textMuted;
                }
                return Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(ts.length > 10 ? ts.substring(11, math.min(19, ts.length)) : ts,
                        style: GoogleFonts.sourceCodePro(
                          fontSize: 10, color: AriaTheme.textSubtle, height: 1.6)),
                      const SizedBox(width: 8),
                      Expanded(child: Text(msg,
                        style: GoogleFonts.sourceCodePro(
                          fontSize: 11, color: logColor, height: 1.5))),
                    ],
                  ),
                );
              },
            ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Shared 3D result section wrapper
// ─────────────────────────────────────────────────────────────

class _ResultSection3d extends StatefulWidget {
  const _ResultSection3d({
    required this.icon,
    required this.title,
    required this.child,
    this.badge,
    this.glowColor,
  });
  final IconData icon;
  final String   title;
  final Widget   child;
  final String?  badge;
  final Color?   glowColor;
  @override
  State<_ResultSection3d> createState() => _ResultSection3dState();
}
class _ResultSection3dState extends State<_ResultSection3d> {
  bool _expanded = true;
  @override
  Widget build(BuildContext context) {
    return Aria3dCard(
      glowColor: widget.glowColor ?? AriaTheme.brandIndigo,
      maxTiltDeg: 4.0,
      child: Container(
        decoration: BoxDecoration(
          color: const Color(0x0A0F1020),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AriaTheme.borderStandard),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          // Header
          GestureDetector(
            onTap: () => setState(() => _expanded = !_expanded),
            child: Container(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: AriaTheme.borderSubtle)),
              ),
              child: Row(children: [
                Icon(widget.icon, size: 15, color: AriaTheme.textMuted),
                const SizedBox(width: 8),
                Text(widget.title, style: AriaTheme.inter(
                  size: 13, weight: FontWeight.w500, color: AriaTheme.textSecondary)),
                if (widget.badge != null) ...[
                  const SizedBox(width: 8),
                  AriaPill(label: widget.badge!, subtle: true),
                ],
                const Spacer(),
                Icon(
                  _expanded ? Icons.keyboard_arrow_up : Icons.keyboard_arrow_down,
                  size: 14, color: AriaTheme.textSubtle),
              ]),
            ),
          ),
          // Body
          if (_expanded)
            Padding(
              padding: const EdgeInsets.all(16),
              child: widget.child,
            ),
        ]),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Documents content
// ─────────────────────────────────────────────────────────────

class _DocumentsContent extends StatefulWidget {
  const _DocumentsContent({required this.controller});
  final AriaController controller;
  @override
  State<_DocumentsContent> createState() => _DocumentsContentState();
}
class _DocumentsContentState extends State<_DocumentsContent> {
  static const _pageSize = 8;
  int _shown = _pageSize;

  @override
  Widget build(BuildContext context) {
    final docs    = widget.controller.documents;
    final visible = docs.take(_shown).toList();

    return Column(children: [
      ...visible.asMap().entries.map((e) => _DocRow3d(doc: e.value, idx: e.key)),
      if (_shown < docs.length) ...[
        const SizedBox(height: 10),
        Center(child: GestureDetector(
          onTap: () => setState(() => _shown += _pageSize),
          child: AriaPill(
            label: 'Show ${math.min(_pageSize, docs.length - _shown)} more',
            subtle: true,
          ),
        )),
      ],
    ]);
  }
}

class _DocRow3d extends StatefulWidget {
  const _DocRow3d({required this.doc, required this.idx});
  final Map<String, dynamic> doc;
  final int idx;
  @override
  State<_DocRow3d> createState() => _DocRow3dState();
}
class _DocRow3dState extends State<_DocRow3d> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final doc     = widget.doc;
    final title   = doc['title']   as String? ?? 'Untitled';
    final url     = doc['url']     as String? ?? '';
    final summary = doc['summary'] as String? ?? doc['text'] as String? ?? '';
    final score   = (doc['relevance_score'] as num?)?.toStringAsFixed(2) ?? '';
    final source  = doc['source_type'] as String? ?? doc['platform'] as String? ?? '';

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: const Color(0x05FFFFFF),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AriaTheme.borderSubtle),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        GestureDetector(
          onTap: () => setState(() => _expanded = !_expanded),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
            child: Row(children: [
              Container(
                width: 20, height: 20,
                decoration: BoxDecoration(
                  color: AriaTheme.brandIndigo.withAlpha(15),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: AriaTheme.brandIndigo.withAlpha(40)),
                ),
                child: Center(child: Text('${widget.idx + 1}',
                  style: AriaTheme.inter(size: 9, color: AriaTheme.brandIndigo))),
              ),
              const SizedBox(width: 10),
              Expanded(child: Text(title,
                style: AriaTheme.inter(size: 13, weight: FontWeight.w500,
                  color: AriaTheme.textSecondary),
                maxLines: 1, overflow: TextOverflow.ellipsis)),
              if (score.isNotEmpty) ...[
                const SizedBox(width: 8),
                AriaPill(label: score, color: AriaTheme.statusEmerald),
              ],
              if (source.isNotEmpty) ...[
                const SizedBox(width: 6),
                AriaPill(label: source, subtle: true),
              ],
              const SizedBox(width: 8),
              Icon(
                _expanded ? Icons.keyboard_arrow_up : Icons.keyboard_arrow_down,
                size: 14, color: AriaTheme.textSubtle),
            ]),
          ),
        ),
        if (_expanded) ...[
          Container(height: 1, color: AriaTheme.borderSubtle,
            margin: const EdgeInsets.symmetric(horizontal: 12)),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              if (summary.isNotEmpty) ...[
                Text(ariaExcerpt(summary, 60),
                  style: AriaTheme.inter(size: 12, color: AriaTheme.textMuted, height: 1.6)),
                const SizedBox(height: 8),
              ],
              if (url.isNotEmpty)
                SelectableText(url,
                  style: AriaTheme.inter(size: 11, color: AriaTheme.brandIndigo)),
            ]),
          ),
        ],
      ]),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Ensemble content
// ─────────────────────────────────────────────────────────────

class _EnsembleContent extends StatelessWidget {
  const _EnsembleContent({required this.controller});
  final AriaController controller;
  @override
  Widget build(BuildContext context) {
    final docs = controller.ensembleDocuments;
    return Column(children: docs.asMap().entries.map((e) {
      final doc    = e.value;
      final model  = doc['model'] as String? ?? 'Model ${e.key + 1}';
      final answer = doc['answer'] as String?
          ?? doc['summary'] as String?
          ?? doc['text'] as String? ?? '';
      return Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AriaTheme.accentViolet.withAlpha(8),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: AriaTheme.accentViolet.withAlpha(30)),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.smart_toy_outlined, size: 13, color: AriaTheme.accentViolet),
            const SizedBox(width: 6),
            Text(model, style: AriaTheme.inter(
              size: 11, weight: FontWeight.w500, color: AriaTheme.accentViolet)),
          ]),
          const SizedBox(height: 8),
          SelectableText(answer,
            style: AriaTheme.inter(size: 13, color: AriaTheme.textSecondary, height: 1.6)),
        ]),
      );
    }).toList());
  }
}

// ─────────────────────────────────────────────────────────────
// Knowledge graph content
// ─────────────────────────────────────────────────────────────

class _KnowledgeGraphContent extends StatelessWidget {
  const _KnowledgeGraphContent({required this.controller});
  final AriaController controller;
  @override
  Widget build(BuildContext context) {
    final c         = controller;
    final kg        = c.knowledgeGraph;
    final entities  = c.topEntities;
    final nodeCount = (kg['node_count'] as num? ?? 0).toInt();
    final edgeCount = (kg['edge_count'] as num? ?? 0).toInt();

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        _MetaMini(label: 'Nodes', value: '$nodeCount'),
        const SizedBox(width: 16),
        _MetaMini(label: 'Edges', value: '$edgeCount'),
        if (c.contradictionsCount > 0) ...[
          const SizedBox(width: 16),
          _MetaMini(label: 'Conflicts', value: '${c.contradictionsCount}',
            accent: AriaTheme.statusAmber),
        ],
      ]),
      if (entities.isNotEmpty) ...[
        const SizedBox(height: 14),
        Text('TOP ENTITIES',
          style: AriaTheme.inter(size: 9, weight: FontWeight.w600,
            color: AriaTheme.textSubtle, letterSpacing: 0.8)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 6, runSpacing: 6,
          children: entities.take(20).map((e) {
            final name = e['name'] as String? ?? '';
            final type = e['type'] as String? ?? '';
            return Container(
              padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
              decoration: BoxDecoration(
                color: AriaTheme.statusEmerald.withAlpha(10),
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: AriaTheme.statusEmerald.withAlpha(30)),
              ),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Text(name, style: AriaTheme.inter(
                  size: 12, color: AriaTheme.textSecondary)),
                if (type.isNotEmpty) ...[
                  const SizedBox(width: 5),
                  Text(type, style: AriaTheme.inter(
                    size: 10, color: AriaTheme.textSubtle)),
                ],
              ]),
            );
          }).toList(),
        ),
      ],
    ]);
  }
}

class _MetaMini extends StatelessWidget {
  const _MetaMini({required this.label, required this.value, this.accent});
  final String label, value;
  final Color? accent;
  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(value, style: AriaTheme.inter(
        size: 20, weight: FontWeight.w500,
        color: accent ?? AriaTheme.textPrimary, height: 1.1)),
      Text(label, style: AriaTheme.inter(size: 10, color: AriaTheme.textSubtle)),
    ]);
  }
}

// ─────────────────────────────────────────────────────────────
// Gap analysis content
// ─────────────────────────────────────────────────────────────

class _GapAnalysisContent extends StatelessWidget {
  const _GapAnalysisContent({required this.controller});
  final AriaController controller;
  @override
  Widget build(BuildContext context) {
    final ga   = controller.gapAnalysis;
    final gaps = List<dynamic>.from(ga['gaps'] as List? ?? []);

    return Column(children: gaps.take(10).map((g) {
      final gap = g as Map<String, dynamic>;
      final q   = gap['question'] as String? ?? gap['gap'] as String? ?? '';
      final sev = gap['severity'] as String? ?? 'medium';
      Color sevColor;
      switch (sev) {
        case 'high':   sevColor = AriaTheme.statusRed;   break;
        case 'medium': sevColor = AriaTheme.statusAmber; break;
        default:       sevColor = AriaTheme.textMuted;
      }
      return Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: sevColor.withAlpha(8),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: sevColor.withAlpha(30)),
        ),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(
            width: 3, height: 36,
            margin: const EdgeInsets.only(right: 10, top: 2),
            decoration: BoxDecoration(
              color: sevColor,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          Expanded(child: Text(q,
            style: AriaTheme.inter(size: 12, color: AriaTheme.textMuted, height: 1.6))),
          const SizedBox(width: 8),
          AriaPill(label: sev, color: sevColor),
        ]),
      );
    }).toList());
  }
}

// ─────────────────────────────────────────────────────────────
// Image gallery content
// ─────────────────────────────────────────────────────────────

class _ImageGalleryContent extends StatelessWidget {
  const _ImageGalleryContent({required this.controller});
  final AriaController controller;
  @override
  Widget build(BuildContext context) {
    final images = controller.collectedImages;
    return Wrap(
      spacing: 8, runSpacing: 8,
      children: images.take(24).map((img) {
        final url = img['url'] as String? ?? '';
        final alt = img['alt'] as String? ?? '';
        return Container(
          width: 100, height: 80,
          decoration: BoxDecoration(
            color: AriaTheme.bg3,
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: AriaTheme.borderSubtle),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(5),
            child: url.isNotEmpty
                ? Image.network(url, fit: BoxFit.cover,
                    errorBuilder: (ctx, err, st) => _ImgFallback3d(alt: alt))
                : _ImgFallback3d(alt: alt),
          ),
        );
      }).toList(),
    );
  }
}

class _ImgFallback3d extends StatelessWidget {
  const _ImgFallback3d({required this.alt});
  final String alt;
  @override
  Widget build(BuildContext context) {
    return Column(mainAxisAlignment: MainAxisAlignment.center, children: [
      const Icon(Icons.image_not_supported_outlined,
        size: 18, color: AriaTheme.textSubtle),
      if (alt.isNotEmpty) ...[
        const SizedBox(height: 4),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4),
          child: Text(alt,
            style: AriaTheme.inter(size: 9, color: AriaTheme.textSubtle),
            textAlign: TextAlign.center, maxLines: 2, overflow: TextOverflow.ellipsis),
        ),
      ],
    ]);
  }
}

// ─────────────────────────────────────────────────────────────
// ARIA 5.0 chip (domain, country, citation)
// ─────────────────────────────────────────────────────────────

class _Aria5Chip extends StatefulWidget {
  const _Aria5Chip({
    required this.icon,
    required this.label,
    required this.active,
    required this.color,
    required this.onTap,
  });
  final IconData icon;
  final String   label;
  final bool     active;
  final Color    color;
  final VoidCallback onTap;
  @override
  State<_Aria5Chip> createState() => _Aria5ChipState();
}
class _Aria5ChipState extends State<_Aria5Chip> {
  bool _hover = false;
  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit:  (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 120),
          padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
          decoration: BoxDecoration(
            color: widget.active
                ? widget.color.withAlpha(20)
                : _hover ? const Color(0x0AFFFFFF) : const Color(0x05FFFFFF),
            borderRadius: BorderRadius.circular(5),
            border: Border.all(
              color: widget.active
                  ? widget.color.withAlpha(60)
                  : _hover ? AriaTheme.borderStandard : AriaTheme.borderSubtle,
            ),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(widget.icon, size: 11,
              color: widget.active ? widget.color : AriaTheme.textSubtle),
            const SizedBox(width: 5),
            Text(widget.label, style: AriaTheme.mono(
              size: 10, weight: FontWeight.w500,
              color: widget.active ? widget.color : AriaTheme.textMuted,
              letterSpacing: 0.2)),
          ]),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Domain selector bottom sheet
// ─────────────────────────────────────────────────────────────

class _DomainSheet extends StatelessWidget {
  const _DomainSheet({required this.controller});
  final AriaController controller;

  static const _domains = [
    ('health',     Icons.local_hospital_outlined,  'Health & Medicine'),
    ('finance',    Icons.bar_chart_outlined,        'Finance & Economy'),
    ('jobs',       Icons.work_outline,              'Jobs & Labor'),
    ('technology', Icons.computer_outlined,         'Technology'),
    ('environment',Icons.eco_outlined,              'Environment'),
    ('policy',     Icons.policy_outlined,           'Policy & Law'),
    ('education',  Icons.school_outlined,           'Education'),
    ('research',   Icons.science_outlined,          'Research & Science'),
    ('trade',      Icons.swap_horiz_outlined,       'Trade & Business'),
    ('security',   Icons.security_outlined,         'Security & Defense'),
    ('culture',    Icons.palette_outlined,          'Culture & Society'),
    ('media',      Icons.newspaper_outlined,        'Media & News'),
  ];

  @override
  Widget build(BuildContext context) {
    final c = controller;
    return StatefulBuilder(
      builder: (ctx, setState) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Text('Research Domains', style: AriaTheme.inter(
                size: 15, weight: FontWeight.w500, color: AriaTheme.textPrimary)),
            const Spacer(),
            if (c.selectedDomains.isNotEmpty)
              GestureDetector(
                onTap: () {
                  for (final d in List.from(c.selectedDomains)) { c.toggleDomain(d); }
                  setState(() {});
                },
                child: Text('Clear', style: AriaTheme.inter(size: 12, color: AriaTheme.statusRed)),
              ),
          ]),
          const SizedBox(height: 6),
          Text('Select domain-specific collectors to activate',
              style: AriaTheme.inter(size: 12, color: AriaTheme.textSubtle)),
          const SizedBox(height: 16),
          Wrap(spacing: 8, runSpacing: 8, children: _domains.map((d) {
            final selected = c.selectedDomains.contains(d.$1);
            return GestureDetector(
              onTap: () { c.toggleDomain(d.$1); setState(() {}); },
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 120),
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: selected ? AriaTheme.brandIndigo.withAlpha(20) : const Color(0x08FFFFFF),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(
                    color: selected ? AriaTheme.brandIndigo.withAlpha(60) : AriaTheme.borderSubtle),
                ),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Icon(d.$2, size: 13,
                    color: selected ? AriaTheme.brandIndigo : AriaTheme.textMuted),
                  const SizedBox(width: 6),
                  Text(d.$3, style: AriaTheme.inter(
                    size: 12, weight: FontWeight.w500,
                    color: selected ? AriaTheme.brandIndigo : AriaTheme.textMuted)),
                ]),
              ),
            );
          }).toList()),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: GestureDetector(
              onTap: () => Navigator.of(context).pop(),
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 10),
                decoration: BoxDecoration(
                  color: AriaTheme.brandIndigo,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Center(child: Text('Done',
                  style: AriaTheme.inter(size: 13, weight: FontWeight.w500,
                    color: AriaTheme.textPrimary))),
              ),
            ),
          ),
          const SizedBox(height: 8),
        ]),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Country selector bottom sheet
// ─────────────────────────────────────────────────────────────

class _CountrySheet extends StatelessWidget {
  const _CountrySheet({required this.controller});
  final AriaController controller;

  static const _regions = [
    ('Global', ['GLOBAL']),
    ('Asia Pacific', ['IN', 'CN', 'JP', 'KR', 'SG', 'AU', 'ID', 'PH', 'VN', 'TH', 'MY', 'BD']),
    ('North America', ['US', 'CA', 'MX']),
    ('Europe', ['EU', 'GB', 'DE', 'FR', 'IT', 'ES', 'NL', 'SE', 'NO', 'DK', 'PL', 'CH']),
    ('Latin America', ['BR', 'AR', 'CO', 'CL', 'PE']),
    ('Middle East & Africa', ['NG', 'ZA', 'EG', 'KE', 'ET', 'SA', 'AE', 'IL']),
  ];

  @override
  Widget build(BuildContext context) {
    final c = controller;
    return StatefulBuilder(
      builder: (ctx, setState) => SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Text('Country Filter', style: AriaTheme.inter(
                size: 15, weight: FontWeight.w500, color: AriaTheme.textPrimary)),
            const Spacer(),
            if (c.selectedCountries.isNotEmpty)
              GestureDetector(
                onTap: () {
                  for (final cc in List.from(c.selectedCountries)) { c.toggleCountry(cc); }
                  setState(() {});
                },
                child: Text('Clear', style: AriaTheme.inter(size: 12, color: AriaTheme.statusRed)),
              ),
          ]),
          const SizedBox(height: 6),
          Text('Activate country-specific data sources (World Bank, WHO, Eurostat, etc.)',
              style: AriaTheme.inter(size: 12, color: AriaTheme.textSubtle)),
          const SizedBox(height: 16),
          ..._regions.map((region) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(region.$1.toUpperCase(), style: AriaTheme.inter(
                size: 9, weight: FontWeight.w600, color: AriaTheme.textSubtle, letterSpacing: 0.8)),
            const SizedBox(height: 8),
            Wrap(spacing: 6, runSpacing: 6, children: region.$2.map((code) {
              final selected = c.selectedCountries.contains(code);
              return GestureDetector(
                onTap: () { c.toggleCountry(code); setState(() {}); },
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 100),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: selected ? AriaTheme.statusEmerald.withAlpha(20) : const Color(0x08FFFFFF),
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(
                      color: selected ? AriaTheme.statusEmerald.withAlpha(60) : AriaTheme.borderSubtle),
                  ),
                  child: Text(code, style: AriaTheme.inter(
                    size: 12, weight: FontWeight.w500,
                    color: selected ? AriaTheme.statusEmerald : AriaTheme.textMuted)),
                ),
              );
            }).toList()),
            const SizedBox(height: 14),
          ])),
          SizedBox(
            width: double.infinity,
            child: GestureDetector(
              onTap: () => Navigator.of(context).pop(),
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 10),
                decoration: BoxDecoration(
                  color: AriaTheme.brandIndigo,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Center(child: Text('Done',
                  style: AriaTheme.inter(size: 13, weight: FontWeight.w500,
                    color: AriaTheme.textPrimary))),
              ),
            ),
          ),
          const SizedBox(height: 8),
        ]),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Methodology section — shown in run output when available
// ─────────────────────────────────────────────────────────────

class _MethodologyContent extends StatelessWidget {
  const _MethodologyContent({required this.controller});
  final AriaController controller;

  @override
  Widget build(BuildContext context) {
    final m = controller.methodology;
    if (m.isEmpty) {
      return Text('Methodology data not available for this run.',
          style: AriaTheme.inter(size: 12, color: AriaTheme.textSubtle));
    }

    final method     = m['collection_method'] as String? ?? '';
    final domains    = List<String>.from(m['domains'] as List? ?? []);
    final countries  = List<String>.from(m['countries'] as List? ?? []);
    final sources    = List<String>.from(m['sources_activated'] as List? ?? []);
    final queries    = List<String>.from(m['queries'] as List? ?? []);
    final llmModel   = m['llm_model'] as String? ?? '';
    final duration   = m['duration_seconds'] as num?;
    final citations  = m['citations_resolved'] as int? ?? 0;
    final depth      = m['depth'] as String? ?? '';

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      // Method badges row
      Wrap(spacing: 8, runSpacing: 8, children: [
        if (method.isNotEmpty)
          _MethBadge(label: method, color: AriaTheme.brandIndigo),
        if (depth.isNotEmpty)
          _MethBadge(label: 'Depth: $depth', color: AriaTheme.textMuted),
        if (duration != null)
          _MethBadge(label: '${duration.toStringAsFixed(0)}s', color: AriaTheme.textSubtle),
        if (citations > 0)
          _MethBadge(label: '$citations citations', color: AriaTheme.accentViolet),
      ]),

      if (domains.isNotEmpty) ...[
        const SizedBox(height: 14),
        Text('DOMAINS', style: AriaTheme.inter(size: 9, weight: FontWeight.w600,
            color: AriaTheme.textSubtle, letterSpacing: 0.8)),
        const SizedBox(height: 6),
        Wrap(spacing: 6, runSpacing: 6, children: domains.map((d) =>
          _MethBadge(label: d, color: AriaTheme.brandIndigo)).toList()),
      ],

      if (countries.isNotEmpty) ...[
        const SizedBox(height: 12),
        Text('COUNTRIES', style: AriaTheme.inter(size: 9, weight: FontWeight.w600,
            color: AriaTheme.textSubtle, letterSpacing: 0.8)),
        const SizedBox(height: 6),
        Wrap(spacing: 6, runSpacing: 6, children: countries.map((cc) =>
          _MethBadge(label: cc, color: AriaTheme.statusEmerald)).toList()),
      ],

      if (sources.isNotEmpty) ...[
        const SizedBox(height: 12),
        Text('SOURCES ACTIVATED', style: AriaTheme.inter(size: 9, weight: FontWeight.w600,
            color: AriaTheme.textSubtle, letterSpacing: 0.8)),
        const SizedBox(height: 6),
        Wrap(spacing: 6, runSpacing: 6, children: sources.map((s) =>
          _MethBadge(label: s, color: AriaTheme.textMuted)).toList()),
      ],

      if (queries.isNotEmpty) ...[
        const SizedBox(height: 12),
        Text('QUERIES USED (${queries.length})', style: AriaTheme.inter(size: 9,
            weight: FontWeight.w600, color: AriaTheme.textSubtle, letterSpacing: 0.8)),
        const SizedBox(height: 6),
        ...queries.take(8).map((q) => Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Container(width: 3, height: 3, margin: const EdgeInsets.only(top: 5, right: 8),
              decoration: const BoxDecoration(shape: BoxShape.circle, color: AriaTheme.textSubtle)),
            Expanded(child: Text(q, style: AriaTheme.inter(size: 12, color: AriaTheme.textMuted, height: 1.5))),
          ]),
        )),
      ],

      if (llmModel.isNotEmpty) ...[
        const SizedBox(height: 12),
        Text('PROCESSING', style: AriaTheme.inter(size: 9, weight: FontWeight.w600,
            color: AriaTheme.textSubtle, letterSpacing: 0.8)),
        const SizedBox(height: 6),
        Row(children: [
          const Icon(Icons.smart_toy_outlined, size: 13, color: AriaTheme.accentViolet),
          const SizedBox(width: 6),
          Text(llmModel, style: AriaTheme.inter(size: 12, color: AriaTheme.textMuted)),
        ]),
      ],
    ]);
  }
}

class _MethBadge extends StatelessWidget {
  const _MethBadge({required this.label, required this.color});
  final String label;
  final Color  color;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withAlpha(15),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withAlpha(40)),
      ),
      child: Text(label, style: AriaTheme.inter(size: 11, color: color)),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Download content
// ─────────────────────────────────────────────────────────────

class _DownloadContent extends StatelessWidget {
  const _DownloadContent({required this.controller});
  final AriaController controller;
  @override
  Widget build(BuildContext context) {
    final c = controller;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Download your research run as various formats.',
        style: AriaTheme.inter(size: 12, color: AriaTheme.textSubtle)),
      const SizedBox(height: 14),
      Wrap(spacing: 8, runSpacing: 8, children: [
        _DlBtn(label: 'Raw JSON',   icon: Icons.data_object,
          loading: c.isDownloading('raw_json'),
          result: c.downloadResult('raw_json'),  onTap: c.saveRawJson),
        _DlBtn(label: 'Raw CSV',    icon: Icons.table_chart_outlined,
          loading: c.isDownloading('raw_csv'),
          result: c.downloadResult('raw_csv'),   onTap: c.saveRawCsv),
        _DlBtn(label: 'Clean JSON', icon: Icons.data_object,
          loading: c.isDownloading('clean_json'),
          result: c.downloadResult('clean_json'), onTap: c.saveCleanJson),
        _DlBtn(label: 'Clean CSV',  icon: Icons.table_chart_outlined,
          loading: c.isDownloading('clean_csv'),
          result: c.downloadResult('clean_csv'), onTap: c.saveCleanCsv),
        _DlBtn(label: 'Markdown',   icon: Icons.description_outlined,
          loading: c.isDownloading('clean_md'),
          result: c.downloadResult('clean_md'),  onTap: c.saveCleanMarkdown),
        _DlBtn(label: 'Full ZIP',   icon: Icons.folder_zip_outlined,
          loading: c.isDownloading('zip'),
          result: c.downloadResult('zip'),        onTap: c.saveZip,
          primary: true),
      ]),
    ]);
  }
}

class _DlBtn extends StatelessWidget {
  const _DlBtn({
    required this.label,
    required this.icon,
    required this.loading,
    required this.result,
    required this.onTap,
    this.primary = false,
  });
  final String   label;
  final IconData icon;
  final bool     loading;
  final String   result;
  final VoidCallback onTap;
  final bool     primary;

  @override
  Widget build(BuildContext context) {
    final hasResult = result.isNotEmpty && !result.startsWith('Error');
    final hasError  = result.startsWith('Error');

    Color borderColor;
    if (hasError) {
      borderColor = AriaTheme.statusRed.withAlpha(80);
    } else if (hasResult) {
      borderColor = AriaTheme.statusEmerald.withAlpha(80);
    } else if (primary) {
      borderColor = AriaTheme.brandIndigo.withAlpha(120);
    } else {
      borderColor = AriaTheme.borderStandard;
    }

    return GestureDetector(
      onTap: loading ? null : onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: primary ? AriaTheme.brandIndigo.withAlpha(20) : const Color(0x05FFFFFF),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: borderColor),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          loading
              ? const SizedBox(width: 12, height: 12,
                  child: CircularProgressIndicator(
                    strokeWidth: 1.5, color: AriaTheme.textMuted))
              : Icon(hasResult ? Icons.check : icon, size: 13,
                  color: hasError   ? AriaTheme.statusRed
                      : hasResult   ? AriaTheme.statusEmerald
                      : primary     ? AriaTheme.brandIndigo
                      : AriaTheme.textMuted),
          const SizedBox(width: 6),
          Text(label, style: AriaTheme.inter(
            size: 12, weight: FontWeight.w500,
            color: hasError   ? AriaTheme.statusRed
                : hasResult   ? AriaTheme.statusEmerald
                : primary     ? AriaTheme.brandIndigo
                : AriaTheme.textMuted)),
        ]),
      ),
    );
  }
}
