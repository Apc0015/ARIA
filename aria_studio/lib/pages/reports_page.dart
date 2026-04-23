// ARIA Studio — Reports Page
// Consolidated reporting view: Documents, Statistics, Exports, Analysis
// Merged from aria-report (React) into native Flutter

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/aria_controller.dart';
import '../theme/aria_theme.dart';
import '../widgets/effects_3d.dart';
import '../widgets/shared.dart';
import 'document_detail_page.dart';

class ReportsPage extends StatefulWidget {
  const ReportsPage({super.key, required this.runId});
  final String runId;

  @override
  State<ReportsPage> createState() => _ReportsPageState();
}

class _ReportsPageState extends State<ReportsPage>
    with SingleTickerProviderStateMixin {
  late final AnimationController _entranceCtrl;
  late final Animation<double>   _entranceFade;
  late final Animation<Offset>   _entranceSlide;

  int _tab = 0; // 0=Documents 1=Statistics 2=Exports 3=Analysis

  @override
  void initState() {
    super.initState();
    _entranceCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 420));
    _entranceFade  = CurvedAnimation(parent: _entranceCtrl, curve: Curves.easeOut);
    _entranceSlide = Tween<Offset>(begin: const Offset(0, 0.015), end: Offset.zero)
        .animate(CurvedAnimation(parent: _entranceCtrl, curve: Curves.easeOut));
    _entranceCtrl.forward();

    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AriaController>().loadRunDetail(widget.runId);
    });
  }

  @override
  void dispose() {
    _entranceCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c   = context.watch<AriaController>();
    final run = c.runDetailResult;

    return Scaffold(
      backgroundColor: AriaTheme.bg0,
      body: FadeTransition(
        opacity: _entranceFade,
        child: SlideTransition(
          position: _entranceSlide,
          child: Stack(children: [
            const Positioned.fill(
              child: Opacity(opacity: 0.25, child: Aria3dStarField()),
            ),
            Column(children: [
              _ReportsTopBar(run: run, onBack: () => Navigator.of(context).pop()),
              Expanded(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(width: 220, child: _RunInfoSidebar(run: run)),
                    Container(width: 1, color: AriaTheme.borderSubtle),
                    Expanded(
                      child: Column(children: [
                        _ReportsTabBar(
                          current: _tab,
                          docCount: c.runDetailDocuments.length,
                          onChange: (i) => setState(() => _tab = i),
                        ),
                        Expanded(child: _buildTab(c, run)),
                      ]),
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

  Widget _buildTab(AriaController c, Map<String, dynamic> run) {
    switch (_tab) {
      case 0: return _DocumentsTab(run: run, onDocTap: _openDoc);
      case 1: return _StatisticsTab(run: run, documents: c.runDetailDocuments);
      case 2: return _ExportsTab(runId: widget.runId);
      case 3: return _AnalysisTab(
          kg: c.runDetailKg,
          gaps: c.runDetailGaps,
          images: c.runDetailImages,
        );
      default: return const SizedBox();
    }
  }

  void _openDoc(Map<String, dynamic> doc) {
    Navigator.of(context).push(PageRouteBuilder(
      opaque: false,
      pageBuilder: (_, __, ___) => DocumentDetailPage(doc: doc),
      transitionsBuilder: (_, anim, __, child) =>
          FadeTransition(opacity: anim, child: child),
    ));
  }
}

// ─────────────────────────────────────────────────────────────
// Top bar
// ─────────────────────────────────────────────────────────────

class _ReportsTopBar extends StatelessWidget {
  const _ReportsTopBar({required this.run, required this.onBack});
  final Map<String, dynamic> run;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    final topic  = run['topic'] as String? ?? 'Report';
    final status = run['status'] as String? ?? 'unknown';
    final id     = run['id'] as String? ?? run['run_id'] as String? ?? '';

    Color statusColor;
    switch (status) {
      case 'completed': statusColor = AriaTheme.statusEmerald; break;
      case 'failed':    statusColor = AriaTheme.statusRed;     break;
      case 'running':   statusColor = AriaTheme.accentViolet;  break;
      default:          statusColor = AriaTheme.textSubtle;    break;
    }

    return Container(
      height: 52,
      decoration: const BoxDecoration(
        color: Color(0x80080A0F),
        border: Border(bottom: BorderSide(color: AriaTheme.borderSubtle)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(children: [
        GestureDetector(
          onTap: onBack,
          child: const Icon(Icons.arrow_back, size: 16, color: AriaTheme.textMuted),
        ),
        const SizedBox(width: 12),
        Text('ARIA', style: AriaTheme.inter(
          size: 18, weight: FontWeight.w700,
          color: AriaTheme.brandIndigo, letterSpacing: 2.5)),
        Text(' / Reports', style: AriaTheme.inter(size: 14, color: AriaTheme.textMuted)),
        const SizedBox(width: 12),
        Container(width: 1, height: 16, color: AriaTheme.borderSubtle),
        const SizedBox(width: 12),
        Flexible(child: Text(topic,
          style: AriaTheme.inter(size: 13, color: AriaTheme.textSecondary),
          overflow: TextOverflow.ellipsis)),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
          decoration: BoxDecoration(
            color: statusColor.withAlpha(15),
            borderRadius: BorderRadius.circular(4),
            border: Border.all(color: statusColor.withAlpha(40)),
          ),
          child: Text(status, style: AriaTheme.inter(size: 10, color: statusColor)),
        ),
        if (id.isNotEmpty) ...[
          const SizedBox(width: 8),
          Text(id.length > 8 ? id.substring(0, 8) : id,
              style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
        ],
      ]),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Run info sidebar
// ─────────────────────────────────────────────────────────────

class _RunInfoSidebar extends StatelessWidget {
  const _RunInfoSidebar({required this.run});
  final Map<String, dynamic> run;

  @override
  Widget build(BuildContext context) {
    final stats    = run['stats'] as Map<String, dynamic>? ?? {};
    final collected = (stats['total_collected'] as num?)?.toInt() ?? (run['documents'] as List?)?.length ?? 0;
    final cleaned   = (stats['total_cleaned'] as num?)?.toInt() ?? 0;
    final sources   = (stats['sources_hit'] as num?)?.toInt() ?? 0;
    final dur       = run['duration_seconds'] as num?;
    final ts        = run['created_at'] as String? ?? '';

    return Container(
      color: const Color(0x050F1020),
      padding: const EdgeInsets.all(14),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _SbHeader('Collection'),
            const SizedBox(height: 10),
            _SbRow(label: 'Collected', value: '$collected'),
            _SbRow(label: 'Cleaned',   value: '$cleaned'),
            _SbRow(label: 'Sources',   value: '$sources'),
            const SizedBox(height: 16),
            _SbHeader('Intelligence'),
            const SizedBox(height: 10),
            _SbRow(label: 'KG Nodes', value: '${run['kg_node_count'] ?? 0}'),
            _SbRow(label: 'KG Edges', value: '${run['kg_edge_count'] ?? 0}'),
            _SbRow(label: 'Gaps',     value: '${run['gaps_count'] ?? 0}'),
            _SbRow(label: 'Images',   value: '${run['images_count'] ?? 0}'),
            const SizedBox(height: 16),
            _SbHeader('Run Info'),
            const SizedBox(height: 10),
            if (ts.isNotEmpty) _SbRow(label: 'Started', value: ts.length > 10 ? ts.substring(0, 10) : ts),
            if (dur != null) _SbRow(label: 'Duration', value: '${dur.toStringAsFixed(0)}s'),
          ],
        ),
      ),
    );
  }
}

class _SbHeader extends StatelessWidget {
  const _SbHeader(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Text(text.toUpperCase(),
    style: AriaTheme.inter(size: 9, weight: FontWeight.w600,
      color: AriaTheme.textSubtle, letterSpacing: 0.9));
}

class _SbRow extends StatelessWidget {
  const _SbRow({required this.label, required this.value});
  final String label, value;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: Row(children: [
      Expanded(child: Text(label,
        style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle))),
      Text(value,
        style: AriaTheme.inter(size: 12, weight: FontWeight.w500, color: AriaTheme.textPrimary)),
    ]),
  );
}

// ─────────────────────────────────────────────────────────────
// Tab bar
// ─────────────────────────────────────────────────────────────

class _ReportsTabBar extends StatelessWidget {
  const _ReportsTabBar({
    required this.current,
    required this.docCount,
    required this.onChange,
  });
  final int current, docCount;
  final ValueChanged<int> onChange;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 40,
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AriaTheme.borderSubtle)),
      ),
      child: Row(children: [
        _TabBtn(label: 'Documents',  count: docCount, active: current == 0, onTap: () => onChange(0)),
        _TabBtn(label: 'Statistics', count: 0,        active: current == 1, onTap: () => onChange(1)),
        _TabBtn(label: 'Exports',    count: 0,        active: current == 2, onTap: () => onChange(2)),
        _TabBtn(label: 'Analysis',   count: 0,        active: current == 3, onTap: () => onChange(3)),
      ]),
    );
  }
}

class _TabBtn extends StatefulWidget {
  const _TabBtn({required this.label, required this.count, required this.active, required this.onTap});
  final String label;
  final int    count;
  final bool   active;
  final VoidCallback onTap;
  @override
  State<_TabBtn> createState() => _TabBtnState();
}

class _TabBtnState extends State<_TabBtn> {
  bool _hover = false;
  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit:  (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            border: Border(bottom: BorderSide(
              color: widget.active ? AriaTheme.brandIndigo
                  : _hover ? AriaTheme.borderStandard : Colors.transparent,
              width: 1.5,
            )),
          ),
          child: Row(children: [
            Text(widget.label, style: AriaTheme.inter(
              size: 13,
              weight: widget.active ? FontWeight.w500 : FontWeight.w400,
              color: widget.active ? AriaTheme.textPrimary
                  : _hover ? AriaTheme.textMuted : AriaTheme.textSubtle)),
            if (widget.count > 0) ...[
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                decoration: BoxDecoration(
                  color: widget.active ? AriaTheme.brandIndigo.withAlpha(20) : AriaTheme.bg3,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text('${widget.count}', style: AriaTheme.inter(
                  size: 10,
                  color: widget.active ? AriaTheme.brandIndigo : AriaTheme.textSubtle)),
              ),
            ],
          ]),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Tab 0: Documents
// ─────────────────────────────────────────────────────────────

class _DocumentsTab extends StatefulWidget {
  const _DocumentsTab({required this.run, required this.onDocTap});
  final Map<String, dynamic> run;
  final void Function(Map<String, dynamic>) onDocTap;
  @override
  State<_DocumentsTab> createState() => _DocumentsTabState();
}

class _DocumentsTabState extends State<_DocumentsTab> {
  static const _pageSize = 20;
  int    _shown        = _pageSize;
  String _sortBy       = 'relevance';
  String _filterSource = '';
  String _filterType   = '';
  final  _searchCtrl   = TextEditingController();
  String _search       = '';

  @override
  void dispose() { _searchCtrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    var docs = List<Map<String, dynamic>>.from(widget.run['documents'] as List? ?? []);

    if (_search.isNotEmpty) {
      final q = _search.toLowerCase();
      docs = docs.where((d) {
        final t = (d['title'] as String? ?? '').toLowerCase();
        final s = (d['summary'] as String? ?? d['text'] as String? ?? '').toLowerCase();
        return t.contains(q) || s.contains(q);
      }).toList();
    }
    if (_filterSource.isNotEmpty) {
      docs = docs.where((d) =>
        (d['source_type'] as String? ?? d['platform'] as String? ?? '') == _filterSource
      ).toList();
    }
    if (_filterType.isNotEmpty) {
      docs = docs.where((d) =>
        (d['content_type'] as String? ?? d['type'] as String? ?? '') == _filterType
      ).toList();
    }

    if (_sortBy == 'relevance') {
      docs.sort((a, b) => ((b['relevance_score'] as num?) ?? 0)
          .compareTo((a['relevance_score'] as num?) ?? 0));
    } else if (_sortBy == 'title') {
      docs.sort((a, b) => (a['title'] as String? ?? '').compareTo(b['title'] as String? ?? ''));
    }

    final visible = docs.take(_shown).toList();
    final sources = docs
        .map((d) => d['source_type'] as String? ?? d['platform'] as String? ?? '')
        .where((s) => s.isNotEmpty).toSet().toList()..sort();
    final types = docs
        .map((d) => d['content_type'] as String? ?? d['type'] as String? ?? '')
        .where((t) => t.isNotEmpty).toSet().toList()..sort();

    return Column(children: [
      Container(
        padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
        child: Row(children: [
          SizedBox(
            width: 200,
            child: AriaInputField(
              controller: _searchCtrl,
              hint: 'Search documents…',
              icon: Icons.search,
              onChanged: (v) => setState(() { _search = v; _shown = _pageSize; }),
            ),
          ),
          const SizedBox(width: 8),
          _Select(
            value: _sortBy,
            options: const {'relevance': 'Relevance', 'title': 'Title'},
            onChange: (v) => setState(() { _sortBy = v; _shown = _pageSize; }),
          ),
          if (sources.isNotEmpty) ...[
            const SizedBox(width: 8),
            _Select(
              value: _filterSource,
              options: {'': 'All Sources', ...Map.fromEntries(sources.map((s) => MapEntry(s, s)))},
              onChange: (v) => setState(() { _filterSource = v; _shown = _pageSize; }),
            ),
          ],
          if (types.isNotEmpty) ...[
            const SizedBox(width: 8),
            _Select(
              value: _filterType,
              options: {'': 'All Types', ...Map.fromEntries(types.map((t) => MapEntry(t, t)))},
              onChange: (v) => setState(() { _filterType = v; _shown = _pageSize; }),
            ),
          ],
          const Spacer(),
          Text('${docs.length} docs',
            style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
        ]),
      ),
      const Divider(height: 1, color: AriaTheme.borderSubtle),
      Expanded(
        child: ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: visible.length + (_shown < docs.length ? 1 : 0),
          itemBuilder: (ctx, i) {
            if (i >= visible.length) {
              return Center(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: GestureDetector(
                    onTap: () => setState(() => _shown += _pageSize),
                    child: AriaPill(label: 'Show $_pageSize more', subtle: true),
                  ),
                ),
              );
            }
            final doc = visible[i];
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: _DocCard(doc: doc, idx: i, onTap: () => widget.onDocTap(doc)),
            );
          },
        ),
      ),
    ]);
  }
}

class _DocCard extends StatefulWidget {
  const _DocCard({required this.doc, required this.idx, required this.onTap});
  final Map<String, dynamic> doc;
  final int idx;
  final VoidCallback onTap;
  @override
  State<_DocCard> createState() => _DocCardState();
}

class _DocCardState extends State<_DocCard> {
  bool _hover = false;
  @override
  Widget build(BuildContext context) {
    final doc     = widget.doc;
    final title   = doc['title'] as String? ?? 'Untitled';
    final summary = doc['summary'] as String? ?? doc['text'] as String? ?? '';
    final score   = (doc['relevance_score'] as num?)?.toStringAsFixed(2) ?? '';
    final source  = doc['source_type'] as String? ?? doc['platform'] as String? ?? '';
    final ctype   = doc['content_type'] as String? ?? doc['type'] as String? ?? '';
    final lang    = doc['language'] as String? ?? '';

    Color scoreColor = AriaTheme.textSubtle;
    if (score.isNotEmpty) {
      final v = double.tryParse(score) ?? 0;
      if (v >= 0.7)      scoreColor = AriaTheme.statusEmerald;
      else if (v >= 0.4) scoreColor = AriaTheme.statusAmber;
      else               scoreColor = AriaTheme.statusRed;
    }

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit:  (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 120),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: _hover ? AriaTheme.cardBgHover : AriaTheme.cardBg,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: _hover ? AriaTheme.borderStandard : AriaTheme.borderSubtle),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Container(
                width: 22, height: 22,
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
                maxLines: 2, overflow: TextOverflow.ellipsis)),
              if (score.isNotEmpty) ...[
                const SizedBox(width: 8),
                AriaPill(label: score, color: scoreColor),
              ],
            ]),
            if (summary.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(ariaExcerpt(summary, 40),
                style: AriaTheme.inter(size: 12, color: AriaTheme.textMuted, height: 1.5),
                maxLines: 3, overflow: TextOverflow.ellipsis),
            ],
            const SizedBox(height: 10),
            Row(children: [
              if (source.isNotEmpty) ...[AriaPill(label: source, subtle: true), const SizedBox(width: 6)],
              if (ctype.isNotEmpty)  ...[AriaPill(label: ctype, subtle: true),  const SizedBox(width: 6)],
              if (lang.isNotEmpty)   ...[AriaPill(label: lang, subtle: true),   const SizedBox(width: 6)],
              const Spacer(),
              Icon(Icons.open_in_new, size: 12,
                color: _hover ? AriaTheme.brandIndigo : AriaTheme.textSubtle),
            ]),
          ]),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Tab 1: Statistics
// ─────────────────────────────────────────────────────────────

class _StatisticsTab extends StatelessWidget {
  const _StatisticsTab({required this.run, required this.documents});
  final Map<String, dynamic>       run;
  final List<Map<String, dynamic>> documents;

  @override
  Widget build(BuildContext context) {
    final stats     = run['stats'] as Map<String, dynamic>? ?? {};
    final collected = (stats['total_collected'] as num?)?.toInt() ?? documents.length;
    final cleaned   = (stats['total_cleaned']   as num?)?.toInt() ?? 0;
    final srcHit    = (stats['sources_hit']      as num?)?.toInt() ?? 0;
    final dur       = run['duration_seconds'] as num?;
    final kgNodes   = run['kg_node_count'] as int? ?? 0;
    final kgEdges   = run['kg_edge_count'] as int? ?? 0;
    final gapCount  = run['gaps_count']    as int? ?? 0;
    final imgCount  = run['images_count']  as int? ?? 0;

    // Compute per-source breakdown
    final sourceMap = <String, int>{};
    for (final d in documents) {
      final s = d['source_type'] as String? ?? d['platform'] as String? ?? 'unknown';
      sourceMap[s] = (sourceMap[s] ?? 0) + 1;
    }
    final sortedSources = sourceMap.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    // Content type breakdown
    final typeMap = <String, int>{};
    for (final d in documents) {
      final t = d['content_type'] as String? ?? d['type'] as String? ?? 'unknown';
      typeMap[t] = (typeMap[t] ?? 0) + 1;
    }
    final sortedTypes = typeMap.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    // Score stats
    final scores = documents
        .map((d) => (d['relevance_score'] as num?)?.toDouble())
        .whereType<double>()
        .toList();
    final avgScore = scores.isEmpty ? 0.0 : scores.reduce((a, b) => a + b) / scores.length;
    final maxScore = scores.isEmpty ? 0.0 : scores.reduce((a, b) => a > b ? a : b);
    final minScore = scores.isEmpty ? 0.0 : scores.reduce((a, b) => a < b ? a : b);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        // Metric cards grid
        AriaSectionHeader(title: 'Overview'),
        const SizedBox(height: 12),
        Wrap(
          spacing: 10, runSpacing: 10,
          children: [
            _MetricCard(label: 'Collected', value: '$collected', icon: Icons.download_outlined, color: AriaTheme.brandIndigo),
            _MetricCard(label: 'Cleaned',   value: '$cleaned',   icon: Icons.cleaning_services_outlined, color: AriaTheme.statusEmerald),
            _MetricCard(label: 'Sources Hit', value: '$srcHit',  icon: Icons.hub_outlined, color: AriaTheme.accentViolet),
            if (dur != null)
              _MetricCard(label: 'Duration', value: '${dur.toStringAsFixed(0)}s', icon: Icons.timer_outlined, color: AriaTheme.statusAmber),
            _MetricCard(label: 'KG Nodes', value: '$kgNodes', icon: Icons.account_tree_outlined, color: AriaTheme.brandIndigo),
            _MetricCard(label: 'KG Edges', value: '$kgEdges', icon: Icons.device_hub_outlined,   color: AriaTheme.accentViolet),
            _MetricCard(label: 'Gaps',     value: '$gapCount', icon: Icons.find_in_page_outlined, color: AriaTheme.statusAmber),
            _MetricCard(label: 'Images',   value: '$imgCount', icon: Icons.image_outlined,         color: AriaTheme.textMuted),
          ],
        ),

        if (scores.isNotEmpty) ...[
          const SizedBox(height: 24),
          AriaSectionHeader(title: 'Relevance Scores'),
          const SizedBox(height: 12),
          AriaCard(
            padding: const EdgeInsets.all(16),
            child: Column(children: [
              Row(children: [
                _ScoreStat(label: 'Average', value: avgScore.toStringAsFixed(2), color: _scoreColor(avgScore)),
                const SizedBox(width: 24),
                _ScoreStat(label: 'Highest', value: maxScore.toStringAsFixed(2), color: AriaTheme.statusEmerald),
                const SizedBox(width: 24),
                _ScoreStat(label: 'Lowest',  value: minScore.toStringAsFixed(2), color: AriaTheme.statusRed),
                const SizedBox(width: 24),
                _ScoreStat(label: 'Total',   value: '${scores.length}',           color: AriaTheme.textMuted),
              ]),
              const SizedBox(height: 16),
              _ScoreDistributionBar(scores: scores),
            ]),
          ),
        ],

        if (sortedSources.isNotEmpty) ...[
          const SizedBox(height: 24),
          AriaSectionHeader(title: 'Source Breakdown'),
          const SizedBox(height: 12),
          AriaCard(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: sortedSources.take(10).map((e) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _BarRow(
                  label: e.key,
                  count: e.value,
                  total: documents.length,
                  color: AriaTheme.brandIndigo,
                ),
              )).toList(),
            ),
          ),
        ],

        if (sortedTypes.isNotEmpty) ...[
          const SizedBox(height: 24),
          AriaSectionHeader(title: 'Content Types'),
          const SizedBox(height: 12),
          AriaCard(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: sortedTypes.take(8).map((e) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _BarRow(
                  label: e.key,
                  count: e.value,
                  total: documents.length,
                  color: AriaTheme.accentViolet,
                ),
              )).toList(),
            ),
          ),
        ],

        const SizedBox(height: 24),
      ]),
    );
  }

  Color _scoreColor(double v) {
    if (v >= 0.7)      return AriaTheme.statusEmerald;
    else if (v >= 0.4) return AriaTheme.statusAmber;
    return AriaTheme.statusRed;
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });
  final String label, value;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 140,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withAlpha(8),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withAlpha(30)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, size: 14, color: color.withAlpha(180)),
          const Spacer(),
        ]),
        const SizedBox(height: 8),
        Text(value,
          style: AriaTheme.inter(size: 26, weight: FontWeight.w500, color: color, height: 1.1)),
        const SizedBox(height: 3),
        Text(label, style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
      ]),
    );
  }
}

class _ScoreStat extends StatelessWidget {
  const _ScoreStat({required this.label, required this.value, required this.color});
  final String label, value;
  final Color  color;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(value, style: AriaTheme.inter(
        size: 24, weight: FontWeight.w500, color: color, height: 1.1)),
      Text(label, style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
    ],
  );
}

class _ScoreDistributionBar extends StatelessWidget {
  const _ScoreDistributionBar({required this.scores});
  final List<double> scores;

  @override
  Widget build(BuildContext context) {
    // Bucket: 0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0
    final buckets = List<int>.filled(5, 0);
    for (final s in scores) {
      final i = (s * 5).floor().clamp(0, 4);
      buckets[i]++;
    }
    final maxBucket = buckets.reduce((a, b) => a > b ? a : b);
    final labels = ['0–0.2', '0.2–0.4', '0.4–0.6', '0.6–0.8', '0.8–1.0'];
    final colors = [AriaTheme.statusRed, AriaTheme.statusAmber, AriaTheme.statusAmber,
                    AriaTheme.statusEmerald, AriaTheme.statusEmerald];

    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: List.generate(5, (i) {
        final fraction = maxBucket == 0 ? 0.0 : buckets[i] / maxBucket;
        return Expanded(child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 3),
          child: Column(children: [
            Text('${buckets[i]}',
              style: AriaTheme.inter(size: 10, color: AriaTheme.textSubtle)),
            const SizedBox(height: 4),
            AnimatedContainer(
              duration: const Duration(milliseconds: 600),
              height: 60 * fraction + 4,
              decoration: BoxDecoration(
                color: colors[i].withAlpha(180),
                borderRadius: BorderRadius.circular(3),
              ),
            ),
            const SizedBox(height: 4),
            Text(labels[i],
              style: AriaTheme.inter(size: 9, color: AriaTheme.textSubtle),
              textAlign: TextAlign.center),
          ]),
        ));
      }),
    );
  }
}

class _BarRow extends StatelessWidget {
  const _BarRow({
    required this.label,
    required this.count,
    required this.total,
    required this.color,
  });
  final String label;
  final int    count, total;
  final Color  color;

  @override
  Widget build(BuildContext context) {
    final frac = total == 0 ? 0.0 : count / total;
    return Row(children: [
      SizedBox(
        width: 120,
        child: Text(label,
          style: AriaTheme.inter(size: 12, color: AriaTheme.textSecondary),
          overflow: TextOverflow.ellipsis),
      ),
      const SizedBox(width: 10),
      Expanded(child: ClipRRect(
        borderRadius: BorderRadius.circular(3),
        child: LinearProgressIndicator(
          value: frac,
          minHeight: 6,
          backgroundColor: AriaTheme.bg3,
          valueColor: AlwaysStoppedAnimation<Color>(color.withAlpha(160)),
        ),
      )),
      const SizedBox(width: 10),
      SizedBox(width: 36,
        child: Text('$count',
          style: AriaTheme.inter(size: 11, weight: FontWeight.w500,
            color: AriaTheme.textMuted),
          textAlign: TextAlign.right)),
    ]);
  }
}

// ─────────────────────────────────────────────────────────────
// Tab 2: Exports
// ─────────────────────────────────────────────────────────────

class _ExportsTab extends StatelessWidget {
  const _ExportsTab({required this.runId});
  final String runId;

  static const _formats = [
    (
      key: 'raw_json',
      label: 'Raw JSON',
      desc: 'Original collected documents with full metadata',
      icon: Icons.data_object,
      color: AriaTheme.textMuted,
    ),
    (
      key: 'clean_json',
      label: 'Clean JSON',
      desc: 'Processed documents with relevance scores and extracted data',
      icon: Icons.cleaning_services_outlined,
      color: AriaTheme.brandIndigo,
    ),
    (
      key: 'clean_csv',
      label: 'CSV Spreadsheet',
      desc: 'Structured tabular data for spreadsheet analysis',
      icon: Icons.table_chart_outlined,
      color: AriaTheme.statusEmerald,
    ),
    (
      key: 'clean_md',
      label: 'Markdown Report',
      desc: 'Human-readable formatted report for documentation',
      icon: Icons.description_outlined,
      color: AriaTheme.accentViolet,
    ),
    (
      key: 'zip',
      label: 'ZIP Bundle',
      desc: 'Complete archive with all formats and assets',
      icon: Icons.folder_zip_outlined,
      color: AriaTheme.statusAmber,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        AriaSectionHeader(title: 'Download Formats'),
        const SizedBox(height: 4),
        Text('Export your research in multiple formats',
          style: AriaTheme.inter(size: 12, color: AriaTheme.textSubtle)),
        const SizedBox(height: 16),
        ..._formats.map((f) => Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: _ExportCard(
            runId: runId,
            formatKey: f.key,
            label: f.label,
            desc: f.desc,
            icon: f.icon,
            color: f.color,
          ),
        )),
      ]),
    );
  }
}

class _ExportCard extends StatefulWidget {
  const _ExportCard({
    required this.runId,
    required this.formatKey,
    required this.label,
    required this.desc,
    required this.icon,
    required this.color,
  });
  final String   runId, formatKey, label, desc;
  final IconData icon;
  final Color    color;
  @override
  State<_ExportCard> createState() => _ExportCardState();
}

class _ExportCardState extends State<_ExportCard> {
  bool _hover    = false;
  bool _loading  = false;
  bool _done     = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit:  (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: _loading ? null : _download,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 120),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: _hover ? widget.color.withAlpha(10) : AriaTheme.cardBg,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: _hover ? widget.color.withAlpha(50) : AriaTheme.borderSubtle),
          ),
          child: Row(children: [
            Container(
              width: 40, height: 40,
              decoration: BoxDecoration(
                color: widget.color.withAlpha(15),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: widget.color.withAlpha(40)),
              ),
              child: Center(child: Icon(widget.icon, size: 18, color: widget.color)),
            ),
            const SizedBox(width: 14),
            Expanded(child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(widget.label,
                  style: AriaTheme.inter(size: 13, weight: FontWeight.w500,
                    color: AriaTheme.textSecondary)),
                const SizedBox(height: 3),
                Text(widget.desc,
                  style: AriaTheme.inter(size: 12, color: AriaTheme.textSubtle)),
              ],
            )),
            const SizedBox(width: 12),
            if (_loading)
              SizedBox(width: 18, height: 18,
                child: CircularProgressIndicator(strokeWidth: 1.5,
                  color: widget.color))
            else if (_done)
              Icon(Icons.check_circle_outline, size: 18, color: AriaTheme.statusEmerald)
            else
              Icon(Icons.download_outlined, size: 18,
                color: _hover ? widget.color : AriaTheme.textSubtle),
          ]),
        ),
      ),
    );
  }

  Future<void> _download() async {
    setState(() { _loading = true; _done = false; });
    await context.read<AriaController>().downloadRunExport(widget.runId, widget.formatKey);
    if (mounted) setState(() { _loading = false; _done = true; });
  }
}

// ─────────────────────────────────────────────────────────────
// Tab 3: Analysis (KG + Gaps + Images)
// ─────────────────────────────────────────────────────────────

class _AnalysisTab extends StatefulWidget {
  const _AnalysisTab({required this.kg, required this.gaps, required this.images});
  final Map<String, dynamic>       kg;
  final List<Map<String, dynamic>> gaps, images;
  @override
  State<_AnalysisTab> createState() => _AnalysisTabState();
}

class _AnalysisTabState extends State<_AnalysisTab> {
  int _section = 0; // 0=KG 1=Gaps 2=Images

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Container(
        height: 36,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        decoration: const BoxDecoration(
          border: Border(bottom: BorderSide(color: AriaTheme.borderSubtle)),
        ),
        child: Row(children: [
          _SubTabBtn(label: 'Knowledge Graph', active: _section == 0, onTap: () => setState(() => _section = 0)),
          const SizedBox(width: 4),
          _SubTabBtn(label: 'Research Gaps', active: _section == 1, onTap: () => setState(() => _section = 1)),
          const SizedBox(width: 4),
          _SubTabBtn(label: 'Images', active: _section == 2, onTap: () => setState(() => _section = 2)),
        ]),
      ),
      Expanded(child: _section == 0
          ? _KgSection(kg: widget.kg)
          : _section == 1
              ? _GapsSection(gaps: widget.gaps)
              : _ImagesSection(images: widget.images)),
    ]);
  }
}

class _SubTabBtn extends StatelessWidget {
  const _SubTabBtn({required this.label, required this.active, required this.onTap});
  final String label;
  final bool   active;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(
            color: active ? const Color(0x1A5E6AD2) : Colors.transparent,
            borderRadius: BorderRadius.circular(5),
            border: Border.all(color: active ? AriaTheme.brandIndigo : Colors.transparent),
          ),
          child: Text(label, style: AriaTheme.inter(
            size: 11, weight: FontWeight.w500,
            color: active ? AriaTheme.accentViolet : AriaTheme.textSubtle)),
        ),
      ),
    );
  }
}

// Knowledge Graph section

class _KgSection extends StatelessWidget {
  const _KgSection({required this.kg});
  final Map<String, dynamic> kg;

  @override
  Widget build(BuildContext context) {
    final entities  = List<Map<String, dynamic>>.from(kg['entities'] as List? ?? []);
    final nodeCount = kg['node_count'] as int? ?? 0;
    final edgeCount = kg['edge_count'] as int? ?? 0;

    if (entities.isEmpty) {
      return _EmptyState(icon: Icons.hub_outlined, message: 'No knowledge graph data');
    }

    final byType = <String, List<Map<String, dynamic>>>{};
    for (final e in entities) {
      final type = e['type'] as String? ?? 'unknown';
      byType.putIfAbsent(type, () => []).add(e);
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          _KgStat(label: 'Nodes',        value: '$nodeCount'),
          const SizedBox(width: 24),
          _KgStat(label: 'Edges',        value: '$edgeCount'),
          const SizedBox(width: 24),
          _KgStat(label: 'Entity Types', value: '${byType.length}'),
        ]),
        const SizedBox(height: 24),
        ...byType.entries.map((entry) => _EntityGroup(
          type: entry.key, entities: entry.value)),
      ]),
    );
  }
}

class _KgStat extends StatelessWidget {
  const _KgStat({required this.label, required this.value});
  final String label, value;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(value, style: AriaTheme.inter(
        size: 28, weight: FontWeight.w500, color: AriaTheme.textPrimary, height: 1.1)),
      Text(label, style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
    ],
  );
}

class _EntityGroup extends StatefulWidget {
  const _EntityGroup({required this.type, required this.entities});
  final String type;
  final List<Map<String, dynamic>> entities;
  @override
  State<_EntityGroup> createState() => _EntityGroupState();
}

class _EntityGroupState extends State<_EntityGroup> {
  bool _expanded = true;
  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      GestureDetector(
        onTap: () => setState(() => _expanded = !_expanded),
        child: MouseRegion(
          cursor: SystemMouseCursors.click,
          child: Row(children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: AriaTheme.brandIndigo.withAlpha(15),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(widget.type.toUpperCase(), style: AriaTheme.inter(
                size: 9, weight: FontWeight.w600,
                color: AriaTheme.brandIndigo, letterSpacing: 0.8)),
            ),
            const SizedBox(width: 8),
            Text('${widget.entities.length}',
              style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
            const SizedBox(width: 6),
            Icon(_expanded ? Icons.keyboard_arrow_down : Icons.keyboard_arrow_right,
              size: 13, color: AriaTheme.textSubtle),
          ]),
        ),
      ),
      if (_expanded) ...[
        const SizedBox(height: 10),
        Wrap(
          spacing: 8, runSpacing: 8,
          children: widget.entities.map((e) {
            final name  = e['name'] as String? ?? '';
            final count = e['count'] as int? ?? e['frequency'] as int? ?? 0;
            return Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: const Color(0x08FFFFFF),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: AriaTheme.borderStandard),
              ),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Text(name, style: AriaTheme.inter(size: 12, color: AriaTheme.textSecondary)),
                if (count > 0) ...[
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                    decoration: BoxDecoration(color: AriaTheme.bg3, borderRadius: BorderRadius.circular(999)),
                    child: Text('$count', style: AriaTheme.inter(size: 10, color: AriaTheme.textSubtle)),
                  ),
                ],
              ]),
            );
          }).toList(),
        ),
      ],
      const SizedBox(height: 20),
    ]);
  }
}

// Gaps section

class _GapsSection extends StatelessWidget {
  const _GapsSection({required this.gaps});
  final List<Map<String, dynamic>> gaps;

  @override
  Widget build(BuildContext context) {
    if (gaps.isEmpty) {
      return _EmptyState(
        icon: Icons.check_circle_outline,
        message: 'No research gaps identified',
        sub: 'Your research appears comprehensive!',
        color: AriaTheme.statusEmerald,
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: gaps.length,
      itemBuilder: (ctx, i) {
        final gap = gaps[i];
        final question       = gap['question']       as String? ?? gap['gap'] as String? ?? '';
        final sev            = gap['severity']       as String? ?? 'medium';
        final recommendation = gap['recommendation'] as String? ?? '';
        Color sevColor;
        switch (sev) {
          case 'high':   sevColor = AriaTheme.statusRed;   break;
          case 'medium': sevColor = AriaTheme.statusAmber;  break;
          default:       sevColor = AriaTheme.textMuted;    break;
        }
        return Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: sevColor.withAlpha(8),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: sevColor.withAlpha(25)),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Container(width: 3, height: 24,
                decoration: BoxDecoration(color: sevColor, borderRadius: BorderRadius.circular(2))),
              const SizedBox(width: 12),
              Expanded(child: Text(question, style: AriaTheme.inter(
                size: 13, color: AriaTheme.textSecondary, height: 1.5))),
              const SizedBox(width: 8),
              AriaPill(label: sev, color: sevColor),
            ]),
            if (recommendation.isNotEmpty) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AriaTheme.bg2, borderRadius: BorderRadius.circular(6)),
                child: Row(children: [
                  const Icon(Icons.lightbulb_outline, size: 13, color: AriaTheme.statusAmber),
                  const SizedBox(width: 8),
                  Expanded(child: Text(recommendation, style: AriaTheme.inter(
                    size: 12, color: AriaTheme.textMuted, height: 1.5))),
                ]),
              ),
            ],
          ]),
        );
      },
    );
  }
}

// Images section

class _ImagesSection extends StatelessWidget {
  const _ImagesSection({required this.images});
  final List<Map<String, dynamic>> images;

  @override
  Widget build(BuildContext context) {
    if (images.isEmpty) {
      return const _EmptyState(icon: Icons.image_outlined, message: 'No images collected');
    }
    return GridView.builder(
      padding: const EdgeInsets.all(16),
      gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
        maxCrossAxisExtent: 200,
        mainAxisSpacing: 8,
        crossAxisSpacing: 8,
        childAspectRatio: 1.3,
      ),
      itemCount: images.length,
      itemBuilder: (ctx, i) {
        final img = images[i];
        return _ImageTile(
          url:    img['url']    as String? ?? '',
          alt:    img['alt']    as String? ?? img['caption'] as String? ?? '',
          source: img['source'] as String? ?? '',
        );
      },
    );
  }
}

class _ImageTile extends StatefulWidget {
  const _ImageTile({required this.url, required this.alt, required this.source});
  final String url, alt, source;
  @override
  State<_ImageTile> createState() => _ImageTileState();
}

class _ImageTileState extends State<_ImageTile> {
  bool _hover = false;
  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit:  (_) => setState(() => _hover = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 120),
        decoration: BoxDecoration(
          color: AriaTheme.bg2,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: _hover ? AriaTheme.borderStandard : AriaTheme.borderSubtle),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(7),
          child: Stack(fit: StackFit.expand, children: [
            if (widget.url.isNotEmpty)
              Image.network(widget.url, fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => _ImgFallback(alt: widget.alt))
            else
              _ImgFallback(alt: widget.alt),
            if (_hover && widget.alt.isNotEmpty)
              Positioned(
                left: 0, right: 0, bottom: 0,
                child: Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(gradient: LinearGradient(
                    begin: Alignment.topCenter, end: Alignment.bottomCenter,
                    colors: [Colors.transparent, Colors.black.withAlpha(180)],
                  )),
                  child: Text(widget.alt,
                    style: AriaTheme.inter(size: 10, color: Colors.white),
                    maxLines: 2, overflow: TextOverflow.ellipsis),
                ),
              ),
          ]),
        ),
      ),
    );
  }
}

class _ImgFallback extends StatelessWidget {
  const _ImgFallback({required this.alt});
  final String alt;
  @override
  Widget build(BuildContext context) {
    return Container(
      color: AriaTheme.bg3,
      child: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.image_not_supported_outlined, size: 24, color: AriaTheme.textSubtle),
        if (alt.isNotEmpty) ...[
          const SizedBox(height: 4),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Text(alt,
              style: AriaTheme.inter(size: 9, color: AriaTheme.textSubtle),
              textAlign: TextAlign.center, maxLines: 2, overflow: TextOverflow.ellipsis),
          ),
        ],
      ])),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Shared helpers
// ─────────────────────────────────────────────────────────────

class _Select extends StatelessWidget {
  const _Select({required this.value, required this.options, required this.onChange});
  final String value;
  final Map<String, String> options;
  final ValueChanged<String> onChange;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: const Color(0x08FFFFFF),
        borderRadius: BorderRadius.circular(5),
        border: Border.all(color: AriaTheme.borderStandard),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: value,
          isDense: true,
          dropdownColor: AriaTheme.bg2,
          style: AriaTheme.inter(size: 11, color: AriaTheme.textSecondary),
          icon: const Icon(Icons.arrow_drop_down, size: 14, color: AriaTheme.textSubtle),
          items: options.entries.map((e) => DropdownMenuItem(
            value: e.key, child: Text(e.value))).toList(),
          onChanged: (v) { if (v != null) onChange(v); },
        ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({
    required this.icon,
    required this.message,
    this.sub,
    this.color = AriaTheme.textSubtle,
  });
  final IconData icon;
  final String   message;
  final String?  sub;
  final Color    color;

  @override
  Widget build(BuildContext context) {
    return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, size: 40, color: color),
      const SizedBox(height: 12),
      Text(message, style: AriaTheme.inter(size: 14, color: AriaTheme.textMuted)),
      if (sub != null) ...[
        const SizedBox(height: 4),
        Text(sub!, style: AriaTheme.inter(size: 12, color: AriaTheme.textSubtle)),
      ],
    ]));
  }
}
