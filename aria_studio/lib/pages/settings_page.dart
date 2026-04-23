// ARIA Studio — Settings Page
// "Deep Space Research Terminal" 3D design aesthetic
// Glass panels · 3D tilt cards · star field · glowing headers · 3D tab rail

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import '../state/aria_controller.dart';
import '../theme/aria_theme.dart';
import '../widgets/effects_3d.dart';
import '../widgets/shared.dart';

// ─────────────────────────────────────────────────────────────
// Page root
// ─────────────────────────────────────────────────────────────

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});
  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage>
    with TickerProviderStateMixin {

  int _section = 0;

  late final AnimationController _entranceCtrl;
  late final Animation<double>   _entranceFade;
  late final Animation<Offset>   _entranceSlide;

  static const _tabs = [
    (Icons.language_outlined,          'Sources'),
    (Icons.auto_awesome_outlined,      'Models'),
    (Icons.key_outlined,               'Auth'),
    (Icons.tune_outlined,              'Advanced'),
  ];

  @override
  void initState() {
    super.initState();
    _entranceCtrl = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 420));
    _entranceFade  = CurvedAnimation(parent: _entranceCtrl, curve: Curves.easeOut);
    _entranceSlide = Tween<Offset>(
      begin: const Offset(0, 0.018), end: Offset.zero,
    ).animate(CurvedAnimation(parent: _entranceCtrl, curve: Curves.easeOut));
    _entranceCtrl.forward();
  }

  @override
  void dispose() { _entranceCtrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AriaTheme.bg0,
      body: FadeTransition(
        opacity: _entranceFade,
        child: SlideTransition(
          position: _entranceSlide,
          child: Stack(children: [
            // [0] Subtle star field background
            Positioned.fill(
              child: Opacity(
                opacity: 0.30,
                child: Aria3dStarField(),
              ),
            ),
            // [1] Full UI column
            Column(children: [
              _SettingsTopBar3d(),
              Expanded(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Vertical 3D tab rail
                    _TabRail3d(
                      current: _section,
                      tabs: _tabs,
                      onSelect: (i) => setState(() => _section = i),
                    ),
                    // Scrollable content area
                    Expanded(
                      child: AnimatedSwitcher(
                        duration: const Duration(milliseconds: 240),
                        switchInCurve:  Curves.easeOut,
                        switchOutCurve: Curves.easeIn,
                        transitionBuilder: (child, anim) => FadeTransition(
                          opacity: anim,
                          child: SlideTransition(
                            position: Tween<Offset>(
                              begin: const Offset(0.015, 0), end: Offset.zero,
                            ).animate(anim),
                            child: child,
                          ),
                        ),
                        child: KeyedSubtree(
                          key: ValueKey(_section),
                          child: _sectionWidget(_section),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ]),
          ]),
        ),
      ),
    );
  }

  Widget _sectionWidget(int idx) {
    switch (idx) {
      case 0: return const _SourcesTab();
      case 1: return const _ModelsTab();
      case 2: return const _AuthTab();
      case 3: return const _AdvancedTab();
      default: return const _SourcesTab();
    }
  }
}

// ─────────────────────────────────────────────────────────────
// Top bar — glass panel with back button and title
// ─────────────────────────────────────────────────────────────

class _SettingsTopBar3d extends StatefulWidget {
  @override
  State<_SettingsTopBar3d> createState() => _SettingsTopBar3dState();
}

class _SettingsTopBar3dState extends State<_SettingsTopBar3d> {
  bool _backHover = false;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 52,
      padding: const EdgeInsets.symmetric(horizontal: 20),
      decoration: const BoxDecoration(
        color: Color(0x80080A0F),
        border: Border(bottom: BorderSide(color: AriaTheme.borderSubtle)),
      ),
      child: Row(children: [
        // Back button with 3D hover scale
        MouseRegion(
          cursor: SystemMouseCursors.click,
          onEnter: (_) => setState(() => _backHover = true),
          onExit:  (_) => setState(() => _backHover = false),
          child: GestureDetector(
            onTap: () => Navigator.of(context).pop(),
            child: AnimatedScale(
              scale: _backHover ? 1.08 : 1.0,
              duration: const Duration(milliseconds: 140),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.arrow_back_ios_new_rounded,
                  size: 13,
                  color: _backHover
                      ? AriaTheme.brandIndigo
                      : AriaTheme.textMuted),
                const SizedBox(width: 5),
                Text('Dashboard',
                  style: AriaTheme.inter(
                    size: 13,
                    color: _backHover
                        ? AriaTheme.brandIndigo
                        : AriaTheme.textMuted)),
              ]),
            ),
          ),
        ),
        const SizedBox(width: 14),
        Container(width: 1, height: 16, color: AriaTheme.borderSubtle),
        const SizedBox(width: 14),
        Text('Settings',
          style: AriaTheme.inter(
            size: 16, weight: FontWeight.w500,
            color: AriaTheme.textPrimary)),
        const Spacer(),
        // Subtle ARIA Studio label with glow
        _GlowText(
          'ARIA Studio',
          size: 13,
          color: AriaTheme.textMuted,
          glowColor: AriaTheme.brandIndigo,
        ),
        const SizedBox(width: 4),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
          decoration: BoxDecoration(
            color: AriaTheme.brandIndigo.withAlpha(18),
            borderRadius: BorderRadius.circular(4),
            border: Border.all(color: AriaTheme.brandIndigo.withAlpha(40)),
          ),
          child: Text('Terminal',
            style: AriaTheme.inter(
              size: 10, weight: FontWeight.w500,
              color: AriaTheme.brandIndigo)),
        ),
      ]),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// 3D vertical tab rail
// ─────────────────────────────────────────────────────────────

class _TabRail3d extends StatelessWidget {
  const _TabRail3d({
    required this.current,
    required this.tabs,
    required this.onSelect,
  });
  final int current;
  final List<(IconData, String)> tabs;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 180,
      decoration: BoxDecoration(
        color: const Color(0x60080A0F),
        border: const Border(right: BorderSide(color: AriaTheme.borderSubtle)),
      ),
      padding: const EdgeInsets.fromLTRB(10, 20, 10, 20),
      child: Column(
        children: tabs.asMap().entries.map((e) {
          final active = e.key == current;
          return Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: _Tab3dItem(
              icon: e.value.$1,
              label: e.value.$2,
              active: active,
              onTap: () => onSelect(e.key),
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _Tab3dItem extends StatefulWidget {
  const _Tab3dItem({
    required this.icon,
    required this.label,
    required this.active,
    required this.onTap,
  });
  final IconData icon;
  final String   label;
  final bool     active;
  final VoidCallback onTap;
  @override
  State<_Tab3dItem> createState() => _Tab3dItemState();
}

class _Tab3dItemState extends State<_Tab3dItem> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final active = widget.active;
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit:  (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: Aria3dCard(
          maxTiltDeg: 3.0,
          glowColor: active ? AriaTheme.brandIndigo : null,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: active
                  ? AriaTheme.brandIndigo.withAlpha(20)
                  : _hover
                      ? const Color(0x0AFFFFFF)
                      : Colors.transparent,
              borderRadius: BorderRadius.circular(8),
              border: active
                  ? Border.all(color: AriaTheme.brandIndigo.withAlpha(40))
                  : Border.all(color: Colors.transparent),
            ),
            child: Row(children: [
              Icon(
                widget.icon,
                size: 16,
                color: active
                    ? AriaTheme.brandIndigo
                    : _hover
                        ? AriaTheme.textSecondary
                        : AriaTheme.textMuted,
              ),
              const SizedBox(width: 10),
              Text(
                widget.label,
                style: AriaTheme.inter(
                  size: 13,
                  weight: active ? FontWeight.w500 : FontWeight.w400,
                  color: active
                      ? AriaTheme.textPrimary
                      : _hover
                          ? AriaTheme.textSecondary
                          : AriaTheme.textMuted,
                ),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Shared 3D section card wrapper
// ─────────────────────────────────────────────────────────────

class _SectionCard3d extends StatelessWidget {
  const _SectionCard3d({
    required this.child,
    this.index = 0,
    this.glowColor,
  });
  final Widget child;
  final int    index;
  final Color? glowColor;

  @override
  Widget build(BuildContext context) {
    return Aria3dStagger(
      index: index,
      child: Aria3dCard(
        maxTiltDeg: 3.0,
        glowColor: glowColor ?? AriaTheme.brandIndigo,
        child: Aria3dGlassPanel(
          padding: const EdgeInsets.all(20),
          child: child,
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Glowing section header
// ─────────────────────────────────────────────────────────────

class _SectionHeader3d extends StatelessWidget {
  const _SectionHeader3d(this.title, {this.trailing});
  final String  title;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      // Accent bar
      Container(
        width: 3, height: 16,
        decoration: BoxDecoration(
          color: AriaTheme.brandIndigo,
          borderRadius: BorderRadius.circular(2),
          boxShadow: [
            BoxShadow(
              color: AriaTheme.brandIndigo.withAlpha(120),
              blurRadius: 8,
              spreadRadius: 1,
            ),
          ],
        ),
      ),
      const SizedBox(width: 10),
      _GlowText(
        title,
        size: 13,
        weight: FontWeight.w600,
        color: AriaTheme.textPrimary,
        glowColor: AriaTheme.brandIndigo,
        letterSpacing: 0.5,
      ),
      if (trailing != null) ...[
        const Spacer(),
        trailing!,
      ],
    ]);
  }
}

// ─────────────────────────────────────────────────────────────
// Scrollable content scaffold for each tab
// ─────────────────────────────────────────────────────────────

class _TabScaffold extends StatelessWidget {
  const _TabScaffold({required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 24, 24, 48),
      child: child,
    );
  }
}

// ─────────────────────────────────────────────────────────────
// TAB 0 — Sources  (Free Sources + Platforms merged)
// ─────────────────────────────────────────────────────────────

class _SourcesTab extends StatelessWidget {
  const _SourcesTab();

  @override
  Widget build(BuildContext context) {
    final c = context.watch<AriaController>();
    return _TabScaffold(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Core
          _SectionCard3d(
            index: 0,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _SectionHeader3d('Core Sources'),
                const SizedBox(height: 16),
                AriaSourceRow(label: 'Web Search',      value: c.srcWeb,       icon: Icons.language,                onChanged: c.toggleSrcWeb,       subtitle: 'DuckDuckGo + Bing'),
                AriaSourceRow(label: 'PDF Discovery',   value: c.srcPdf,       icon: Icons.picture_as_pdf_outlined, onChanged: c.toggleSrcPdf,       subtitle: 'Open-access PDFs'),
                AriaSourceRow(label: 'Academic Papers', value: c.srcAcademic,  icon: Icons.science_outlined,        onChanged: c.toggleSrcAcademic,  subtitle: 'arXiv, Semantic Scholar, PubMed'),
                AriaSourceRow(label: 'Wikipedia',       value: c.srcWikipedia, icon: Icons.menu_book_outlined,      onChanged: c.toggleSrcWikipedia, subtitle: 'Wikipedia API'),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // ── Community & Dev
          _SectionCard3d(
            index: 1,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _SectionHeader3d('Community & Dev'),
                const SizedBox(height: 16),
                AriaSourceRow(label: 'Reddit',         value: c.srcReddit,        icon: Icons.forum_outlined,      onChanged: c.toggleSrcReddit,        subtitle: 'Public posts & comments'),
                AriaSourceRow(label: 'Hacker News',    value: c.srcHackernews,    icon: Icons.whatshot_outlined,   onChanged: c.toggleSrcHackernews,    subtitle: 'HN Algolia API'),
                AriaSourceRow(label: 'Stack Overflow', value: c.srcStackoverflow, icon: Icons.help_outline,        onChanged: c.toggleSrcStackoverflow, subtitle: 'Q&A via Stack Exchange API'),
                AriaSourceRow(label: 'GitHub',         value: c.srcGithub,        icon: Icons.code,                onChanged: c.toggleSrcGithub,        subtitle: 'Repos & issues (GITHUB_TOKEN optional)'),
                AriaSourceRow(label: 'Dev.to',         value: c.srcDevto,         icon: Icons.developer_mode,      onChanged: c.toggleSrcDevto,         subtitle: 'Dev.to public API'),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // ── Media & Publishing
          _SectionCard3d(
            index: 2,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _SectionHeader3d('Media & Publishing'),
                const SizedBox(height: 16),
                AriaSourceRow(label: 'YouTube',   value: c.srcYoutube,  icon: Icons.play_circle_outline, onChanged: c.toggleSrcYoutube,  subtitle: 'Captions & metadata'),
                AriaSourceRow(label: 'Medium',    value: c.srcMedium,   icon: Icons.article_outlined,    onChanged: c.toggleSrcMedium,   subtitle: 'Public articles via RSS'),
                AriaSourceRow(label: 'Substack',  value: c.srcSubstack, icon: Icons.email_outlined,      onChanged: c.toggleSrcSubstack, subtitle: 'Newsletter RSS feeds'),
                AriaSourceRow(label: 'RSS Feeds', value: c.srcRss,      icon: Icons.rss_feed,            onChanged: c.toggleSrcRss,      subtitle: 'Custom URLs — configure in Auth tab'),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // ── Specialised
          _SectionCard3d(
            index: 3,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _SectionHeader3d('Specialised'),
                const SizedBox(height: 16),
                AriaSourceRow(label: 'News (RSS + APIs)',    value: c.srcNews,         icon: Icons.newspaper_outlined,       onChanged: c.toggleSrcNews,         subtitle: 'BBC, Reuters, AP, NewsAPI, GNews'),
                AriaSourceRow(label: 'Government (.gov)',    value: c.srcGovernment,   icon: Icons.account_balance_outlined,  onChanged: c.toggleSrcGovernment,   subtitle: 'data.gov, regulations.gov'),
                AriaSourceRow(label: 'Multilingual Search',  value: c.srcMultilingual, icon: Icons.translate,                onChanged: c.toggleSrcMultilingual, subtitle: 'DE, FR, ES, ZH, AR, RU and more'),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // ── Connection / API Server
          _SectionCard3d(
            index: 4,
            child: _ConnectionCardContent(),
          ),
        ],
      ),
    );
  }
}

// Connection card content (extracted so it can own its state)
class _ConnectionCardContent extends StatefulWidget {
  @override
  State<_ConnectionCardContent> createState() => _ConnectionCardContentState();
}

class _ConnectionCardContentState extends State<_ConnectionCardContent> {
  late TextEditingController _urlCtrl;

  @override
  void initState() {
    super.initState();
    _urlCtrl = TextEditingController(
      text: context.read<AriaController>().apiBaseUrl);
  }

  @override
  void dispose() { _urlCtrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final c = context.watch<AriaController>();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionHeader3d(
          'API Connection',
          trailing: Aria3dButton(
            label: 'Reconnect',
            icon: Icons.refresh,
            onTap: c.refreshConnection,
          ),
        ),
        const SizedBox(height: 16),
        AriaInputField(
          controller: _urlCtrl,
          label: 'API Server URL',
          hint: 'http://127.0.0.1:8765',
          icon: Icons.dns_outlined,
          onChanged: c.updateApiBaseUrl,
        ),
        const SizedBox(height: 12),
        Row(children: [
          AriaStatusDot(
            connected: c.isConnected,
            label: c.isConnected ? 'Connected to ARIA API' : 'Not connected',
          ),
        ]),
        if (c.lastValidationMessage.isNotEmpty) ...[
          const SizedBox(height: 12),
          _StatusBanner(
            text: c.lastValidationMessage,
            isOk: c.isConnected,
          ),
        ],
        const SizedBox(height: 16),
        Container(height: 1, color: AriaTheme.borderSubtle),
        const SizedBox(height: 14),
        Text('Start the API server',
          style: AriaTheme.inter(size: 13, weight: FontWeight.w500,
            color: AriaTheme.textSecondary)),
        const SizedBox(height: 8),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: const Color(0x08FFFFFF),
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: AriaTheme.borderSubtle),
          ),
          child: SelectableText(
            'python -m aria.cli --serve-api --api-port 8765',
            style: GoogleFonts.sourceCodePro(
              fontSize: 12,
              color: AriaTheme.textSecondary,
              height: 1.5,
            ),
          ),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────
// TAB 1 — Models
// ─────────────────────────────────────────────────────────────

class _ModelsTab extends StatefulWidget {
  const _ModelsTab();
  @override
  State<_ModelsTab> createState() => _ModelsTabState();
}

class _ModelsTabState extends State<_ModelsTab> {
  final _apiKeyCtrl = TextEditingController();

  @override
  void dispose() { _apiKeyCtrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final c = context.watch<AriaController>();
    return _TabScaffold(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Enable toggle
          _SectionCard3d(
            index: 0,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _SectionHeader3d('AI Ensemble'),
                const SizedBox(height: 14),
                Row(children: [
                  Icon(Icons.psychology_outlined, size: 15, color: AriaTheme.textMuted),
                  const SizedBox(width: 10),
                  Expanded(child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Enable AI Ensemble',
                        style: AriaTheme.inter(size: 13, weight: FontWeight.w500,
                          color: AriaTheme.textSecondary)),
                      Text('Runs LLMs for cleaning, synthesis, gap analysis',
                        style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
                    ],
                  )),
                  Switch(value: c.useLlm, onChanged: c.toggleUseLlm),
                ]),
              ],
            ),
          ),

          if (c.useLlm) ...[
            const SizedBox(height: 16),

            // ── Mode selector
            _SectionCard3d(
              index: 1,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const _SectionHeader3d('Inference Mode'),
                  const SizedBox(height: 14),
                  Row(children: [
                    AriaTabChip(
                      label: 'Cloud',
                      selected: c.llmMode == 'cloud',
                      onTap: () => c.setLlmMode('cloud'),
                    ),
                    const SizedBox(width: 8),
                    AriaTabChip(
                      label: 'Local (Ollama)',
                      selected: c.llmMode == 'local',
                      onTap: () => c.setLlmMode('local'),
                    ),
                  ]),
                ],
              ),
            ),
            const SizedBox(height: 16),

            if (c.llmMode == 'cloud') ...[
              // ── Add provider
              _SectionCard3d(
                index: 2,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const _SectionHeader3d('Add Cloud Provider'),
                    const SizedBox(height: 6),
                    Text('Paste an API key — provider is auto-detected.',
                      style: AriaTheme.inter(size: 12, color: AriaTheme.textSubtle)),
                    const SizedBox(height: 14),
                    Row(children: [
                      Expanded(child: AriaInputField(
                        controller: _apiKeyCtrl,
                        hint: 'sk-... or sk-ant-... or ...',
                        obscure: true,
                        icon: Icons.vpn_key_outlined,
                        onChanged: c.updatePendingApiKey,
                      )),
                      const SizedBox(width: 10),
                      Aria3dButton(
                        label: c.isDetecting ? 'Detecting…' : 'Detect',
                        icon: Icons.auto_fix_high_outlined,
                        loading: c.isDetecting,
                        enabled: !c.isDetecting,
                        onTap: () async {
                          await c.detectProvider();
                          _apiKeyCtrl.clear();
                        },
                      ),
                    ]),
                  ],
                ),
              ),
              const SizedBox(height: 12),

              // ── Provider list
              if (c.cloudProviders.isEmpty)
                _SectionCard3d(
                  index: 3,
                  child: _EmptyHint3d(
                    icon: Icons.add_circle_outline,
                    text: 'No providers added yet. Paste an API key above.',
                  ),
                ),

              ...c.cloudProviders.asMap().entries.map((e) {
                final pi = e.key;
                final p  = e.value;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _SectionCard3d(
                    index: 3 + pi,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(children: [
                          _SectionHeader3d(
                            p.detectedName.isNotEmpty ? p.detectedName : p.detectedProvider,
                          ),
                          const Spacer(),
                          AriaDangerButton(
                            label: 'Remove',
                            onPressed: () => c.removeCloudProvider(pi),
                          ),
                        ]),
                        if (p.availableModels.isNotEmpty) ...[
                          const SizedBox(height: 14),
                          Text('Select models for ensemble:',
                            style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
                          const SizedBox(height: 10),
                          Wrap(spacing: 6, runSpacing: 6,
                            children: p.availableModels.map((m) {
                              final sel = p.selectedModels.contains(m);
                              return GestureDetector(
                                onTap: () => c.toggleCloudModel(pi, m),
                                child: AnimatedContainer(
                                  duration: const Duration(milliseconds: 120),
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 10, vertical: 5),
                                  decoration: BoxDecoration(
                                    color: sel
                                        ? const Color(0x1A5E6AD2)
                                        : AriaTheme.cardBg,
                                    borderRadius: BorderRadius.circular(999),
                                    border: Border.all(
                                      color: sel
                                          ? AriaTheme.brandIndigo
                                          : AriaTheme.borderSubtle),
                                  ),
                                  child: Text(m, style: AriaTheme.inter(
                                    size: 11, weight: FontWeight.w500,
                                    color: sel
                                        ? AriaTheme.accentViolet
                                        : AriaTheme.textMuted)),
                                ),
                              );
                            }).toList(),
                          ),
                        ],
                      ],
                    ),
                  ),
                );
              }),

              if (c.cleaningBrainLabel.isNotEmpty) ...[
                const SizedBox(height: 4),
                _InfoBanner3d(
                  icon: Icons.auto_fix_high_outlined,
                  text: 'Smart cleaning brain: ${c.cleaningBrainLabel}',
                ),
              ],

            ] else ...[
              // ── Ollama local
              _SectionCard3d(
                index: 2,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _SectionHeader3d(
                      'Ollama (Local)',
                      trailing: AriaGhostButton(
                        label: 'Detect',
                        icon: Icons.refresh,
                        onPressed: c.detectOllama,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text('Runs models locally — no API key needed.',
                      style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
                    const SizedBox(height: 14),
                    AriaStatusDot(
                      connected: c.ollamaConnected,
                      label: c.ollamaConnected ? 'Running' : 'Not detected',
                    ),
                    if (c.ollamaAvailableModels.isNotEmpty) ...[
                      const SizedBox(height: 14),
                      Wrap(spacing: 6, runSpacing: 6,
                        children: c.ollamaAvailableModels.map((m) {
                          final sel = c.ollamaSelectedModels.contains(m);
                          return GestureDetector(
                            onTap: () => c.toggleOllamaModel(m),
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 120),
                              padding: const EdgeInsets.symmetric(
                                horizontal: 10, vertical: 5),
                              decoration: BoxDecoration(
                                color: sel
                                    ? const Color(0x1A5E6AD2) : AriaTheme.cardBg,
                                borderRadius: BorderRadius.circular(999),
                                border: Border.all(
                                  color: sel
                                      ? AriaTheme.brandIndigo : AriaTheme.borderSubtle),
                              ),
                              child: Text(m, style: AriaTheme.inter(
                                size: 11, weight: FontWeight.w500,
                                color: sel
                                    ? AriaTheme.accentViolet : AriaTheme.textMuted)),
                            ),
                          );
                        }).toList(),
                      ),
                    ],
                    if (c.ollamaAvailableModels.isEmpty && c.ollamaConnected)
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: _EmptyHint3d(
                          icon: Icons.info_outline,
                          text: 'No models found. Run: ollama pull llama3',
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// TAB 2 — Auth  (Auth Sources + Platforms)
// ─────────────────────────────────────────────────────────────

class _AuthTab extends StatefulWidget {
  const _AuthTab();
  @override
  State<_AuthTab> createState() => _AuthTabState();
}

class _AuthTabState extends State<_AuthTab> {
  final _feedCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _feedCtrl.text = context.read<AriaController>().feedUrlsText;
  }

  @override
  void dispose() { _feedCtrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final c = context.watch<AriaController>();
    return _TabScaffold(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Auth source tiles
          _SectionCard3d(
            index: 0,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _SectionHeader3d('Authenticated Sources'),
                const SizedBox(height: 6),
                Text('Sources requiring credentials or tokens.',
                  style: AriaTheme.inter(size: 12, color: AriaTheme.textSubtle)),
              ],
            ),
          ),
          const SizedBox(height: 12),

          _AuthTile3d(
            index: 1,
            source: 'twitter',
            label: 'Twitter / X',
            icon: Icons.alternate_email,
            enabled: c.srcTwitter,
            state: c.authSourceStates['twitter']!,
            onToggle: c.toggleSrcTwitter,
            onConnect: (creds) => c.connectAuthSource('twitter', creds),
            onDisconnect: () => c.resetAuthSource('twitter'),
            fields: const [
              _Field('token', 'Bearer Token', obscure: true, hint: 'AAAA...'),
            ],
          ),
          const SizedBox(height: 10),

          _AuthTile3d(
            index: 2,
            source: 'linkedin',
            label: 'LinkedIn',
            icon: Icons.business_center_outlined,
            enabled: c.srcLinkedin,
            state: c.authSourceStates['linkedin']!,
            onToggle: c.toggleSrcLinkedin,
            onConnect: (creds) => c.connectAuthSource('linkedin', creds),
            onDisconnect: () => c.resetAuthSource('linkedin'),
            fields: const [
              _Field('username', 'Email',    hint: 'you@email.com'),
              _Field('password', 'Password', obscure: true),
            ],
          ),
          const SizedBox(height: 10),

          _AuthTile3d(
            index: 3,
            source: 'notion',
            label: 'Notion',
            icon: Icons.note_alt_outlined,
            enabled: c.srcNotion,
            state: c.authSourceStates['notion']!,
            onToggle: c.toggleSrcNotion,
            onConnect: (creds) => c.connectAuthSource('notion', creds),
            onDisconnect: () => c.resetAuthSource('notion'),
            fields: const [
              _Field('token', 'Integration Token', obscure: true, hint: 'secret_...'),
            ],
          ),
          const SizedBox(height: 10),

          _AuthTile3d(
            index: 4,
            source: 'slack',
            label: 'Slack',
            icon: Icons.chat_outlined,
            enabled: c.srcSlack,
            state: c.authSourceStates['slack']!,
            onToggle: c.toggleSrcSlack,
            onConnect: (creds) => c.connectAuthSource('slack', creds),
            onDisconnect: () => c.resetAuthSource('slack'),
            fields: const [
              _Field('token', 'Bot Token', obscure: true, hint: 'xoxb-...'),
            ],
          ),
          const SizedBox(height: 10),

          _AuthTile3d(
            index: 5,
            source: 'vimeo',
            label: 'Vimeo',
            icon: Icons.video_library_outlined,
            enabled: c.srcVimeo,
            state: c.authSourceStates['vimeo']!,
            onToggle: c.toggleSrcVimeo,
            onConnect: (creds) => c.connectAuthSource('vimeo', creds),
            onDisconnect: () => c.resetAuthSource('vimeo'),
            fields: const [
              _Field('token', 'Access Token', obscure: true),
            ],
          ),
          const SizedBox(height: 10),

          _AuthTile3d(
            index: 6,
            source: 'zotero',
            label: 'Zotero',
            icon: Icons.library_books_outlined,
            enabled: c.srcZotero,
            state: c.authSourceStates['zotero']!,
            onToggle: c.toggleSrcZotero,
            onConnect: (creds) => c.connectAuthSource('zotero', creds),
            onDisconnect: () => c.resetAuthSource('zotero'),
            fields: const [
              _Field('api_key',      'API Key',      obscure: true, hint: 'from zotero.org/settings/keys'),
              _Field('library_id',   'Library ID',   hint: 'leave empty for personal library'),
              _Field('library_type', 'Library Type', hint: 'user or group (default: user)'),
            ],
          ),
          const SizedBox(height: 16),

          // ── Podcast / RSS feed URLs
          _SectionCard3d(
            index: 7,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SectionHeader3d(
                  'Podcast / RSS / Substack Feeds',
                  trailing: Switch(
                    value: c.srcPodcast,
                    onChanged: c.toggleSrcPodcast,
                  ),
                ),
                const SizedBox(height: 8),
                Text('One URL per line. Used by RSS, Podcast, and Substack collectors.',
                  style: AriaTheme.inter(size: 12, color: AriaTheme.textSubtle)),
                const SizedBox(height: 12),
                AriaInputField(
                  controller: _feedCtrl,
                  hint: 'https://feeds.example.com/feed.xml',
                  maxLines: 4,
                  onChanged: c.updateFeedUrlsText,
                ),
                if (c.feedUrls.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    '${c.feedUrls.length} URL${c.feedUrls.length == 1 ? "" : "s"} detected',
                    style: AriaTheme.inter(size: 11, color: AriaTheme.statusEmerald)),
                ],
              ],
            ),
          ),
          const SizedBox(height: 16),

          // ── Subscription Platforms
          _SectionCard3d(
            index: 8,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _SectionHeader3d('Subscription Platforms'),
                const SizedBox(height: 6),
                Text('Connect institutional access for paywalled academic content.',
                  style: AriaTheme.inter(size: 12, color: AriaTheme.textSubtle)),
              ],
            ),
          ),
          const SizedBox(height: 12),

          ...c.platforms.asMap().entries.map((e) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _PlatformTile3d(
                index: 9 + e.key,
                platform: e.value,
              ),
            );
          }),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// TAB 3 — Advanced  (Smart Cleaning)
// ─────────────────────────────────────────────────────────────

class _AdvancedTab extends StatefulWidget {
  const _AdvancedTab();
  @override
  State<_AdvancedTab> createState() => _AdvancedTabState();
}

class _AdvancedTabState extends State<_AdvancedTab> {
  final _globalCtrl  = TextEditingController();
  final _schemaCtrl  = TextEditingController();
  final _chunkSzCtrl = TextEditingController();
  final _chunkOvCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    final c = context.read<AriaController>();
    _globalCtrl.text  = c.globalInstructions;
    _schemaCtrl.text  = c.outputSchemaJson;
    _chunkSzCtrl.text = c.chunkSize.toString();
    _chunkOvCtrl.text = c.chunkOverlap.toString();
  }

  @override
  void dispose() {
    _globalCtrl.dispose();
    _schemaCtrl.dispose();
    _chunkSzCtrl.dispose();
    _chunkOvCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.watch<AriaController>();
    return _TabScaffold(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Smart cleaning info banner
          _SectionCard3d(
            index: 0,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _SectionHeader3d('Smart Cleaning'),
                const SizedBox(height: 14),
                _InfoBanner3d(
                  icon: Icons.auto_fix_high_outlined,
                  text: 'Smart mode: ARIA automatically detects content type and applies'
                      ' the optimal extraction strategy based on your research goal.'
                      ' Manual instructions below are optional overrides.',
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // ── Global instructions override
          _SectionCard3d(
            index: 1,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _SectionHeader3d('Global Instructions'),
                const SizedBox(height: 14),
                AriaInputField(
                  controller: _globalCtrl,
                  hint: 'Extract only sections about X. Ignore advertisements…',
                  maxLines: 3,
                  onChanged: c.updateGlobalInstructions,
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // ── Output schema
          _SectionCard3d(
            index: 2,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _SectionHeader3d('Output Schema (JSON)'),
                const SizedBox(height: 14),
                Container(
                  decoration: BoxDecoration(
                    color: const Color(0x08FFFFFF),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: AriaTheme.borderSubtle),
                  ),
                  child: TextField(
                    controller: _schemaCtrl,
                    maxLines: 10,
                    onChanged: c.updateOutputSchemaJson,
                    style: GoogleFonts.sourceCodePro(
                      fontSize: 12, color: AriaTheme.textSecondary, height: 1.5),
                    decoration: InputDecoration(
                      border: InputBorder.none,
                      enabledBorder: InputBorder.none,
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(6),
                        borderSide: const BorderSide(color: AriaTheme.brandIndigo),
                      ),
                      contentPadding: const EdgeInsets.all(12),
                      isDense: true,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // ── Chunking
          _SectionCard3d(
            index: 3,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SectionHeader3d(
                  'Document Chunking',
                  trailing: Switch(
                    value: c.chunkingEnabled,
                    onChanged: c.toggleChunking,
                  ),
                ),
                const SizedBox(height: 6),
                Text('Split large documents for better LLM processing.',
                  style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
                if (c.chunkingEnabled) ...[
                  const SizedBox(height: 16),
                  Row(children: [
                    Expanded(child: AriaInputField(
                      controller: _chunkSzCtrl,
                      label: 'Chunk Size (tokens)',
                      hint: '8000',
                      keyboardType: TextInputType.number,
                      onChanged: (v) {
                        final n = int.tryParse(v);
                        if (n != null) c.updateChunkSize(n);
                      },
                    )),
                    const SizedBox(width: 12),
                    Expanded(child: AriaInputField(
                      controller: _chunkOvCtrl,
                      label: 'Overlap (tokens)',
                      hint: '500',
                      keyboardType: TextInputType.number,
                      onChanged: (v) {
                        final n = int.tryParse(v);
                        if (n != null) c.updateChunkOverlap(n);
                      },
                    )),
                  ]),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// 3D Auth Tile — ConnState-aware with glow border
// ─────────────────────────────────────────────────────────────

class _Field {
  const _Field(this.key, this.label, {this.obscure = false, this.hint = ''});
  final String key, label, hint;
  final bool obscure;
}

class _AuthTile3d extends StatefulWidget {
  const _AuthTile3d({
    required this.index,
    required this.source,
    required this.label,
    required this.icon,
    required this.enabled,
    required this.state,
    required this.onToggle,
    required this.onConnect,
    required this.onDisconnect,
    required this.fields,
  });
  final int       index;
  final String    source, label;
  final IconData  icon;
  final bool      enabled;
  final ConnState state;
  final ValueChanged<bool> onToggle;
  final Future<void> Function(Map<String, String>) onConnect;
  final VoidCallback onDisconnect;
  final List<_Field> fields;

  @override
  State<_AuthTile3d> createState() => _AuthTile3dState();
}

class _AuthTile3dState extends State<_AuthTile3d> {
  bool _loading = false;
  late final Map<String, TextEditingController> _ctrls;

  @override
  void initState() {
    super.initState();
    _ctrls = {for (final f in widget.fields) f.key: TextEditingController()};
  }

  @override
  void dispose() {
    for (final c in _ctrls.values) c.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    for (final f in widget.fields) {
      if (_ctrls[f.key]!.text.trim().isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(_snack(
          '${f.label} is required', error: true));
        return;
      }
    }
    setState(() => _loading = true);
    final creds = {for (final f in widget.fields) f.key: _ctrls[f.key]!.text.trim()};
    await widget.onConnect(creds);
    setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final st = widget.state;

    // Glow color based on state
    Color borderColor;
    Color dotColor;
    String dotLabel;
    switch (st) {
      case ConnState.connected:
        borderColor = AriaTheme.statusEmerald.withAlpha(60);
        dotColor    = AriaTheme.statusEmerald;
        dotLabel    = 'Connected';
        break;
      case ConnState.checking:
        borderColor = AriaTheme.statusAmber.withAlpha(50);
        dotColor    = AriaTheme.statusAmber;
        dotLabel    = 'Checking…';
        break;
      case ConnState.failed:
        borderColor = AriaTheme.statusRed.withAlpha(50);
        dotColor    = AriaTheme.statusRed;
        dotLabel    = 'Failed';
        break;
      default:
        borderColor = AriaTheme.borderSubtle;
        dotColor    = AriaTheme.textSubtle;
        dotLabel    = 'Not connected';
    }

    return Aria3dStagger(
      index: widget.index,
      child: Aria3dCard(
        maxTiltDeg: 3.0,
        glowColor: st == ConnState.connected
            ? AriaTheme.statusEmerald
            : AriaTheme.brandIndigo,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          decoration: BoxDecoration(
            // Glass surface
            color: const Color(0x0AFFFFFF),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: borderColor,
              width: st == ConnState.connected ? 1.5 : 1.0,
            ),
            boxShadow: st == ConnState.connected
                ? [
                    BoxShadow(
                      color: AriaTheme.statusEmerald.withAlpha(18),
                      blurRadius: 16,
                      spreadRadius: 1,
                    ),
                  ]
                : null,
          ),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Icon(widget.icon, size: 15, color: AriaTheme.textMuted),
                const SizedBox(width: 8),
                Text(widget.label, style: AriaTheme.inter(
                  size: 13, weight: FontWeight.w500,
                  color: AriaTheme.textSecondary)),
                const SizedBox(width: 10),
                // State indicator
                if (st == ConnState.checking)
                  SizedBox(
                    width: 12, height: 12,
                    child: CircularProgressIndicator(
                      strokeWidth: 1.5,
                      color: AriaTheme.statusAmber,
                    ),
                  )
                else
                  Container(
                    width: 6, height: 6,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: dotColor,
                      boxShadow: st == ConnState.connected
                          ? [BoxShadow(color: dotColor.withAlpha(120), blurRadius: 6)]
                          : null,
                    ),
                  ),
                const SizedBox(width: 6),
                Text(dotLabel, style: AriaTheme.inter(
                  size: 11, color: dotColor)),
                const Spacer(),
                if (st == ConnState.connected) ...[
                  AriaDangerButton(
                    label: 'Disconnect',
                    onPressed: () {
                      widget.onDisconnect();
                      widget.onToggle(false);
                    },
                  ),
                  const SizedBox(width: 8),
                ],
                Switch(value: widget.enabled, onChanged: widget.onToggle),
              ]),

              if (widget.enabled && st != ConnState.connected) ...[
                const SizedBox(height: 14),
                Container(height: 1, color: AriaTheme.borderSubtle),
                const SizedBox(height: 14),
                ...widget.fields.map((f) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: AriaInputField(
                    controller: _ctrls[f.key]!,
                    label: f.label,
                    hint: f.hint,
                    obscure: f.obscure,
                  ),
                )),
                Row(mainAxisAlignment: MainAxisAlignment.end, children: [
                  Aria3dButton(
                    label: 'Connect',
                    icon: Icons.link,
                    loading: _loading,
                    enabled: !_loading,
                    onTap: _loading ? () {} : _connect,
                  ),
                ]),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// 3D Platform Tile
// ─────────────────────────────────────────────────────────────

class _PlatformTile3d extends StatefulWidget {
  const _PlatformTile3d({required this.index, required this.platform});
  final int           index;
  final PlatformEntry platform;

  @override
  State<_PlatformTile3d> createState() => _PlatformTile3dState();
}

class _PlatformTile3dState extends State<_PlatformTile3d> {
  final _userCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  bool   _loading = false;
  String _error   = '';

  @override
  void dispose() {
    _userCtrl.dispose();
    _passCtrl.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    if (_userCtrl.text.trim().isEmpty || _passCtrl.text.trim().isEmpty) {
      setState(() => _error = 'Username and password are required.');
      return;
    }
    setState(() { _loading = true; _error = ''; });
    final c  = context.read<AriaController>();
    final ok = await c.loginPlatform(
      widget.platform.id,
      _userCtrl.text.trim(),
      _passCtrl.text.trim(),
    );
    setState(() {
      _loading = false;
      if (!ok) _error = c.lastValidationMessage.isNotEmpty
          ? c.lastValidationMessage
          : 'Login failed — check credentials';
    });
  }

  @override
  Widget build(BuildContext context) {
    final c = context.watch<AriaController>();
    final p = c.platforms.firstWhere(
      (x) => x.id == widget.platform.id,
      orElse: () => widget.platform,
    );

    return Aria3dStagger(
      index: widget.index,
      child: Aria3dCard(
        maxTiltDeg: 3.0,
        glowColor: p.connected
            ? AriaTheme.statusEmerald
            : AriaTheme.brandIndigo,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          decoration: BoxDecoration(
            color: const Color(0x0AFFFFFF),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: p.connected
                  ? AriaTheme.statusEmerald.withAlpha(60)
                  : AriaTheme.borderSubtle,
              width: p.connected ? 1.5 : 1.0,
            ),
            boxShadow: p.connected
                ? [BoxShadow(
                    color: AriaTheme.statusEmerald.withAlpha(18),
                    blurRadius: 16, spreadRadius: 1)]
                : null,
          ),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                const Icon(Icons.library_books_outlined,
                  size: 15, color: AriaTheme.textMuted),
                const SizedBox(width: 8),
                Text(p.label, style: AriaTheme.inter(
                  size: 13, weight: FontWeight.w500,
                  color: AriaTheme.textSecondary)),
                const Spacer(),
                if (p.connected) ...[
                  Container(
                    width: 6, height: 6,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: AriaTheme.statusEmerald,
                      boxShadow: [BoxShadow(
                        color: AriaTheme.statusEmerald.withAlpha(120),
                        blurRadius: 6)],
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text('Connected', style: AriaTheme.inter(
                    size: 11, color: AriaTheme.statusEmerald)),
                  const SizedBox(width: 10),
                  AriaDangerButton(
                    label: 'Disconnect',
                    onPressed: () => c.disconnectPlatform(p.id),
                  ),
                ] else ...[
                  Container(
                    width: 6, height: 6,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: AriaTheme.textSubtle),
                  ),
                  const SizedBox(width: 6),
                  Text('Not connected', style: AriaTheme.inter(
                    size: 11, color: AriaTheme.textSubtle)),
                ],
              ]),
              if (!p.connected) ...[
                const SizedBox(height: 14),
                Container(height: 1, color: AriaTheme.borderSubtle),
                const SizedBox(height: 14),
                Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Expanded(child: AriaInputField(
                    controller: _userCtrl,
                    label: 'Username / Email',
                    hint: 'you@institution.edu',
                    icon: Icons.person_outline,
                  )),
                  const SizedBox(width: 10),
                  Expanded(child: AriaInputField(
                    controller: _passCtrl,
                    label: 'Password',
                    hint: '••••••••',
                    obscure: true,
                    icon: Icons.lock_outline,
                  )),
                ]),
                if (_error.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  _StatusBanner(text: _error, isOk: false),
                ],
                const SizedBox(height: 14),
                Row(mainAxisAlignment: MainAxisAlignment.end, children: [
                  Aria3dButton(
                    label: 'Connect',
                    icon: Icons.link,
                    loading: _loading,
                    enabled: !_loading,
                    onTap: _loading ? () {} : _login,
                  ),
                ]),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Shared helpers / small widgets
// ─────────────────────────────────────────────────────────────

/// Glow text — subtle text-shadow glow on the label
class _GlowText extends StatelessWidget {
  const _GlowText(
    this.text, {
    this.size   = 13,
    this.weight = FontWeight.w400,
    this.color  = AriaTheme.textMuted,
    this.glowColor = AriaTheme.brandIndigo,
    this.letterSpacing,
  });

  final String  text;
  final double  size;
  final FontWeight weight;
  final Color   color;
  final Color   glowColor;
  final double? letterSpacing;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: AriaTheme.inter(
        size: size,
        weight: weight,
        color: color,
        letterSpacing: letterSpacing,
      ).copyWith(
        shadows: [
          Shadow(
            color: glowColor.withAlpha(60),
            blurRadius: 8,
          ),
        ],
      ),
    );
  }
}

class _InfoBanner3d extends StatelessWidget {
  const _InfoBanner3d({required this.icon, required this.text});
  final IconData icon;
  final String   text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AriaTheme.brandIndigo.withAlpha(12),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AriaTheme.brandIndigo.withAlpha(40)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 14, color: AriaTheme.brandIndigo),
          const SizedBox(width: 8),
          Expanded(child: Text(text,
            style: AriaTheme.inter(size: 12, color: AriaTheme.textMuted, height: 1.6))),
        ],
      ),
    );
  }
}

class _EmptyHint3d extends StatelessWidget {
  const _EmptyHint3d({required this.icon, required this.text});
  final IconData icon;
  final String   text;

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Icon(icon, size: 14, color: AriaTheme.textSubtle),
      const SizedBox(width: 8),
      Expanded(child: Text(text,
        style: AriaTheme.inter(size: 12, color: AriaTheme.textSubtle))),
    ]);
  }
}

class _StatusBanner extends StatelessWidget {
  const _StatusBanner({required this.text, required this.isOk});
  final String text;
  final bool   isOk;

  @override
  Widget build(BuildContext context) {
    final color = isOk ? AriaTheme.statusEmerald : AriaTheme.statusRed;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withAlpha(isOk ? 15 : 18),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withAlpha(isOk ? 50 : 60)),
      ),
      child: Text(text,
        style: AriaTheme.inter(size: 12, color: color)),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Snack helper (file-level)
// ─────────────────────────────────────────────────────────────

SnackBar _snack(String msg, {bool error = false}) => SnackBar(
  content: Text(msg),
  backgroundColor: error ? AriaTheme.statusRed.withAlpha(220) : AriaTheme.bg2,
  behavior: SnackBarBehavior.floating,
  shape: RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(8),
    side: BorderSide(
      color: error
          ? AriaTheme.statusRed.withAlpha(80)
          : AriaTheme.borderStandard),
  ),
);
