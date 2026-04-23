// ARIA Studio — Run Detail Page
// Full results view for a completed run — documents, KG, gaps, images, exports

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/aria_controller.dart';
import '../theme/aria_theme.dart';
import '../widgets/effects_3d.dart';
import '../widgets/shared.dart';
import 'document_detail_page.dart';

class RunDetailPage extends StatefulWidget {
  const RunDetailPage({super.key, required this.runId});
  final String runId;

  @override
  State<RunDetailPage> createState() => _RunDetailPageState();
}

class _RunDetailPageState extends State<RunDetailPage>
    with SingleTickerProviderStateMixin {
  late final AnimationController _entranceCtrl;
  late final Animation<double>   _entranceFade;
  late final Animation<Offset>  _entranceSlide;

  int _tab = 0; // 0=Documents 1=KG 2=Gaps 3=Images

  @override
  void initState() {
    super.initState();
    _entranceCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 420));
    _entranceFade  = CurvedAnimation(parent: _entranceCtrl, curve: Curves.easeOut);
    _entranceSlide = Tween<Offset>(
      begin: const Offset(0, 0.015), end: Offset.zero,
    ).animate(CurvedAnimation(parent: _entranceCtrl, curve: Curves.easeOut));
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
    final c = context.watch<AriaController>();
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
              _RunDetailTopBar(run: run, onBack: () => Navigator.of(context).pop()),
              Expanded(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Left panel — stats
                    SizedBox(
                      width: 220,
                      child: _RunStatsPanel(run: run),
                    ),
                    Container(width: 1, color: AriaTheme.borderSubtle),
                    // Main content
                    Expanded(
                      child: Column(children: [
                        _RunDetailTabBar(
                          current: _tab,
                          docCount: c.runDetailDocuments.length,
                          kgNodeCount: c.runDetailKg['node_count'] as int? ?? 0,
                          gapCount: c.runDetailGaps.length,
                          imageCount: c.runDetailImages.length,
                          onChange: (i) => setState(() => _tab = i),
                        ),
                        Expanded(
                          child: _tab == 0
                              ? _DocumentsTab(run: run, onDocTap: _openDoc)
                              : _tab == 1
                                  ? _KgTab(kg: c.runDetailKg)
                                  : _tab == 2
                                      ? _GapsTab(gaps: c.runDetailGaps)
                                      : _ImagesTab(images: c.runDetailImages),
                        ),
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

  void _openDoc(Map<String, dynamic> doc) {
    Navigator.of(context).push(
      PageRouteBuilder(
        opaque: false,
        pageBuilder: (_, __, ___) => DocumentDetailPage(doc: doc),
        transitionsBuilder: (_, anim, __, child) => FadeTransition(
          opacity: anim,
          child: child,
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Top bar
// ─────────────────────────────────────────────────────────────

class _RunDetailTopBar extends StatelessWidget {
  const _RunDetailTopBar({required this.run, required this.onBack});
  final Map<String, dynamic> run;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    final topic  = run['topic'] as String? ?? 'Run Detail';
    final status = run['status'] as String? ?? 'unknown';
    final id     = run['id'] as String? ?? run['run_id'] as String? ?? '';

    Color statusColor;
    switch (status) {
      case 'completed': statusColor = AriaTheme.statusEmerald; break;
      case 'failed':    statusColor = AriaTheme.statusRed;    break;
      case 'running':   statusColor = AriaTheme.accentViolet; break;
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
        Text(' Studio', style: AriaTheme.inter(size: 14, color: AriaTheme.textMuted)),
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
        const SizedBox(width: 8),
        Text('${id.length > 8 ? id.substring(0, 8) : id}',
            style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
      ]),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Stats panel
// ─────────────────────────────────────────────────────────────

class _RunStatsPanel extends StatelessWidget {
  const _RunStatsPanel({required this.run});
  final Map<String, dynamic> run;

  @override
  Widget build(BuildContext context) {
    final docs     = run['documents'] as List? ?? [];
    final stats    = run['stats'] as Map<String, dynamic>? ?? {};
    final collected = (stats['total_collected'] as num?)?.toInt() ?? docs.length;
    final cleaned   = (stats['total_cleaned'] as num?)?.toInt() ?? 0;
    final sources   = (stats['sources_hit'] as num?)?.toInt() ?? 0;

    return Container(
      color: const Color(0x050F1020),
      padding: const EdgeInsets.all(14),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _SidebarSectionHeader('Collection'),
            const SizedBox(height: 10),
            _StatRow(label: 'Collected', value: '$collected'),
            _StatRow(label: 'Cleaned',   value: '$cleaned'),
            _StatRow(label: 'Sources',   value: '$sources'),
            const SizedBox(height: 16),
            _SidebarSectionHeader('Intelligence'),
            const SizedBox(height: 10),
            _StatRow(label: 'KG Nodes',  value: '${run['kg_node_count'] ?? 0}'),
            _StatRow(label: 'KG Edges',  value: '${run['kg_edge_count'] ?? 0}'),
            _StatRow(label: 'Gaps',      value: '${run['gaps_count'] ?? 0}'),
            _StatRow(label: 'Images',    value: '${run['images_count'] ?? 0}'),
            const SizedBox(height: 16),
            _SidebarSectionHeader('Run Info'),
            const SizedBox(height: 10),
            if (run['created_at'] != null)
              _StatRow(label: 'Started', value: _formatTs(run['created_at'] as String)),
            if (run['duration_seconds'] != null)
              _StatRow(label: 'Duration', value: '${(run['duration_seconds'] as num).toStringAsFixed(0)}s'),
            const SizedBox(height: 16),
            _ExportButtons(runId: run['id'] as String? ?? run['run_id'] as String? ?? ''),
          ],
        ),
      ),
    );
  }

  String _formatTs(String ts) {
    if (ts.length > 10) return ts.substring(0, 10);
    return ts;
  }
}

class _SidebarSectionHeader extends StatelessWidget {
  const _SidebarSectionHeader(this.text);
  final String text;
  @override
  Widget build(BuildContext context) {
    return Text(text.toUpperCase(), style: AriaTheme.inter(
      size: 9, weight: FontWeight.w600,
      color: AriaTheme.textSubtle, letterSpacing: 0.9));
  }
}

class _StatRow extends StatelessWidget {
  const _StatRow({required this.label, required this.value});
  final String label, value;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(children: [
        Expanded(child: Text(label, style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle))),
        Text(value, style: AriaTheme.inter(size: 12, weight: FontWeight.w500, color: AriaTheme.textPrimary)),
      ]),
    );
  }
}

class _ExportButtons extends StatelessWidget {
  const _ExportButtons({required this.runId});
  final String runId;

  @override
  Widget build(BuildContext context) {
    final c = context.read<AriaController>();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SidebarSectionHeader('Downloads'),
        const SizedBox(height: 10),
        ...[
          ('Raw JSON',  Icons.data_object,  AriaTheme.textMuted, () => c.downloadRunExport(runId, 'raw_json')),
          ('Clean JSON', Icons.cleaning_services, AriaTheme.brandIndigo, () => c.downloadRunExport(runId, 'clean_json')),
          ('CSV',       Icons.table_chart_outlined, AriaTheme.statusEmerald, () => c.downloadRunExport(runId, 'clean_csv')),
          ('Markdown',  Icons.description_outlined, AriaTheme.accentViolet, () => c.downloadRunExport(runId, 'clean_md')),
          ('ZIP Bundle',Icons.folder_zip_outlined, AriaTheme.statusAmber, () => c.downloadRunExport(runId, 'zip')),
        ].map((e) => Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: _ExportBtn(
            label: e.$1, icon: e.$2, color: e.$3, onTap: e.$4,
          ),
        )),
      ],
    );
  }
}

class _ExportBtn extends StatefulWidget {
  const _ExportBtn({required this.label, required this.icon, required this.color, required this.onTap});
  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;
  @override
  State<_ExportBtn> createState() => _ExportBtnState();
}

class _ExportBtnState extends State<_ExportBtn> {
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
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
          decoration: BoxDecoration(
            color: _hover ? widget.color.withAlpha(12) : const Color(0x08FFFFFF),
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: _hover ? widget.color.withAlpha(50) : AriaTheme.borderSubtle),
          ),
          child: Row(children: [
            Icon(widget.icon, size: 13, color: _hover ? widget.color : AriaTheme.textSubtle),
            const SizedBox(width: 8),
            Expanded(child: Text(widget.label,
              style: AriaTheme.inter(size: 11, color: _hover ? widget.color : AriaTheme.textMuted))),
          ]),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Tab bar
// ─────────────────────────────────────────────────────────────

class _RunDetailTabBar extends StatelessWidget {
  const _RunDetailTabBar({
    required this.current,
    required this.docCount,
    required this.kgNodeCount,
    required this.gapCount,
    required this.imageCount,
    required this.onChange,
  });
  final int current;
  final int docCount, kgNodeCount, gapCount, imageCount;
  final ValueChanged<int> onChange;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 40,
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AriaTheme.borderSubtle)),
      ),
      child: Row(children: [
        _TabBtn(label: 'Documents', count: docCount, active: current == 0, onTap: () => onChange(0)),
        _TabBtn(label: 'Knowledge Graph', count: kgNodeCount, active: current == 1, onTap: () => onChange(1)),
        _TabBtn(label: 'Research Gaps', count: gapCount, active: current == 2, onTap: () => onChange(2)),
        _TabBtn(label: 'Images', count: imageCount, active: current == 3, onTap: () => onChange(3)),
      ]),
    );
  }
}

class _TabBtn extends StatefulWidget {
  const _TabBtn({required this.label, required this.count, required this.active, required this.onTap});
  final String label;
  final int count;
  final bool active;
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
            border: Border(
              bottom: BorderSide(
                color: widget.active ? AriaTheme.brandIndigo
                    : _hover ? AriaTheme.borderStandard : Colors.transparent,
                width: 1.5,
              ),
            ),
          ),
          child: Row(children: [
            Text(widget.label, style: AriaTheme.inter(
              size: 13, weight: widget.active ? FontWeight.w500 : FontWeight.w400,
              color: widget.active ? AriaTheme.textPrimary
                  : _hover ? AriaTheme.textMuted : AriaTheme.textSubtle)),
            if (widget.count > 0) ...[
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                decoration: BoxDecoration(
                  color: widget.active ? AriaTheme.brandIndigo.withAlpha(20)
                      : AriaTheme.bg3,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text('$widget.count', style: AriaTheme.inter(
                  size: 10, color: widget.active ? AriaTheme.brandIndigo : AriaTheme.textSubtle)),
              ),
            ],
          ]),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Documents tab
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
  int _shown = _pageSize;
  String _sortBy = 'relevance'; // relevance | source | title
  String _filterSource = '';

  @override
  Widget build(BuildContext context) {
    var docs = List<Map<String, dynamic>>.from(
      widget.run['documents'] as List? ?? []);

    if (_filterSource.isNotEmpty) {
      docs = docs.where((d) =>
        (d['source_type'] as String? ?? d['platform'] as String? ?? '') == _filterSource
      ).toList();
    }

    if (_sortBy == 'relevance') {
      docs.sort((a, b) => ((b['relevance_score'] as num?) ?? 0)
          .compareTo((a['relevance_score'] as num?) ?? 0));
    } else if (_sortBy == 'title') {
      docs.sort((a, b) => (a['title'] as String? ?? '')
          .compareTo(b['title'] as String? ?? ''));
    }

    final visible = docs.take(_shown).toList();
    final sources = docs
        .map((d) => d['source_type'] as String? ?? d['platform'] as String? ?? '')
        .where((s) => s.isNotEmpty)
        .toSet()
        .toList()
      ..sort();

    return Column(children: [
      // Toolbar
      Container(
        padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
        child: Row(children: [
          // Sort
          _ToolbarSelect(
            value: _sortBy,
            options: const {'relevance': 'Relevance', 'source': 'Source', 'title': 'Title'},
            onChange: (v) => setState(() { _sortBy = v; _shown = _pageSize; }),
          ),
          const SizedBox(width: 8),
          // Source filter
          if (sources.isNotEmpty)
            _ToolbarSelect(
              value: _filterSource,
              options: {'': 'All Sources', ...Map.fromEntries(sources.map((s) => MapEntry(s, s)))},
              onChange: (v) => setState(() { _filterSource = v; _shown = _pageSize; }),
            ),
          const Spacer(),
          Text('${docs.length} docs', style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
        ]),
      ),
      const Divider(height: 1, color: AriaTheme.borderSubtle),
      // List
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
                    child: AriaPill(
                      label: 'Show ${_pageSize} more',
                      subtle: true,
                    ),
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

class _ToolbarSelect extends StatelessWidget {
  const _ToolbarSelect({required this.value, required this.options, required this.onChange});
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
            value: e.key,
            child: Text(e.value),
          )).toList(),
          onChanged: (v) { if (v != null) onChange(v); },
        ),
      ),
    );
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
    final url     = doc['url'] as String? ?? '';
    final summary = doc['summary'] as String? ?? doc['text'] as String? ?? '';
    final score   = (doc['relevance_score'] as num?)?.toStringAsFixed(2) ?? '';
    final source  = doc['source_type'] as String? ?? doc['platform'] as String? ?? '';
    final ctype   = doc['content_type'] as String? ?? doc['type'] as String? ?? '';

    return MouseRegion(
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
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
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
                  AriaPill(label: score, color: AriaTheme.statusEmerald),
                ],
              ]),
              if (summary.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(summary,
                  style: AriaTheme.inter(size: 12, color: AriaTheme.textMuted, height: 1.5),
                  maxLines: 3, overflow: TextOverflow.ellipsis),
              ],
              const SizedBox(height: 10),
              Row(children: [
                if (source.isNotEmpty) ...[
                  AriaPill(label: source, subtle: true),
                  const SizedBox(width: 6),
                ],
                if (ctype.isNotEmpty) ...[
                  AriaPill(label: ctype, subtle: true),
                  const SizedBox(width: 6),
                ],
                const Spacer(),
                Icon(Icons.open_in_new, size: 12, color: _hover ? AriaTheme.brandIndigo : AriaTheme.textSubtle),
              ]),
            ],
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Knowledge Graph tab
// ─────────────────────────────────────────────────────────────

class _KgTab extends StatelessWidget {
  const _KgTab({required this.kg});
  final Map<String, dynamic> kg;

  @override
  Widget build(BuildContext context) {
    final entities = List<Map<String, dynamic>>.from(
      kg['entities'] as List? ?? []);
    final nodeCount = kg['node_count'] as int? ?? 0;
    final edgeCount = kg['edge_count'] as int? ?? 0;

    if (entities.isEmpty) {
      return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.hub_outlined, size: 40, color: AriaTheme.textSubtle),
        const SizedBox(height: 12),
        Text('No knowledge graph data', style: AriaTheme.inter(size: 14, color: AriaTheme.textMuted)),
      ]));
    }

    // Group entities by type
    final byType = <String, List<Map<String, dynamic>>>{};
    for (final e in entities) {
      final type = e['type'] as String? ?? 'unknown';
      byType.putIfAbsent(type, () => []).add(e);
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Summary row
          Row(children: [
            _KgStat(label: 'Nodes', value: '$nodeCount'),
            const SizedBox(width: 24),
            _KgStat(label: 'Edges', value: '$edgeCount'),
            const SizedBox(width: 24),
            _KgStat(label: 'Entity Types', value: '${byType.length}'),
          ]),
          const SizedBox(height: 24),
          // Entity groups
          ...byType.entries.map((entry) => Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AriaTheme.brandIndigo.withAlpha(15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(entry.key.toUpperCase(), style: AriaTheme.inter(
                    size: 9, weight: FontWeight.w600,
                    color: AriaTheme.brandIndigo, letterSpacing: 0.8)),
                ),
                const SizedBox(width: 8),
                Text('${entry.value.length}',
                    style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
              ]),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8, runSpacing: 8,
                children: entry.value.map((e) {
                  final name = e['name'] as String? ?? '';
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
                          decoration: BoxDecoration(
                            color: AriaTheme.bg3,
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text('$count', style: AriaTheme.inter(size: 10, color: AriaTheme.textSubtle)),
                        ),
                      ],
                    ]),
                  );
                }).toList(),
              ),
              const SizedBox(height: 20),
            ],
          )),
        ],
      ),
    );
  }
}

class _KgStat extends StatelessWidget {
  const _KgStat({required this.label, required this.value});
  final String label, value;
  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(value, style: AriaTheme.inter(
        size: 28, weight: FontWeight.w500, color: AriaTheme.textPrimary, height: 1.1)),
      Text(label, style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
    ]);
  }
}

// ─────────────────────────────────────────────────────────────
// Gaps tab
// ─────────────────────────────────────────────────────────────

class _GapsTab extends StatelessWidget {
  const _GapsTab({required this.gaps});
  final List<Map<String, dynamic>> gaps;

  @override
  Widget build(BuildContext context) {
    if (gaps.isEmpty) {
      return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.check_circle_outline, size: 40, color: AriaTheme.statusEmerald),
        const SizedBox(height: 12),
        Text('No research gaps identified', style: AriaTheme.inter(size: 14, color: AriaTheme.textMuted)),
        const SizedBox(height: 4),
        Text('Your research appears comprehensive!',
            style: AriaTheme.inter(size: 12, color: AriaTheme.textSubtle)),
      ]));
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: gaps.length,
      itemBuilder: (ctx, i) {
        final gap = gaps[i];
        final question = gap['question'] as String? ?? gap['gap'] as String? ?? '';
        final sev = gap['severity'] as String? ?? 'medium';
        final recommendation = gap['recommendation'] as String? ?? '';

        Color sevColor;
        switch (sev) {
          case 'high':   sevColor = AriaTheme.statusRed;    break;
          case 'medium': sevColor = AriaTheme.statusAmber;   break;
          default:       sevColor = AriaTheme.textMuted;     break;
        }

        return Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: sevColor.withAlpha(8),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: sevColor.withAlpha(25)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Container(
                  width: 3, height: 24,
                  decoration: BoxDecoration(
                    color: sevColor, borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(child: Text(question,
                  style: AriaTheme.inter(size: 13, color: AriaTheme.textSecondary, height: 1.5))),
                const SizedBox(width: 8),
                AriaPill(label: sev, color: sevColor),
              ]),
              if (recommendation.isNotEmpty) ...[
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AriaTheme.bg2,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Row(children: [
                    const Icon(Icons.lightbulb_outline, size: 13, color: AriaTheme.statusAmber),
                    const SizedBox(width: 8),
                    Expanded(child: Text(recommendation,
                      style: AriaTheme.inter(size: 12, color: AriaTheme.textMuted, height: 1.5))),
                  ]),
                ),
              ],
            ],
          ),
        );
      },
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Images tab
// ─────────────────────────────────────────────────────────────

class _ImagesTab extends StatelessWidget {
  const _ImagesTab({required this.images});
  final List<Map<String, dynamic>> images;

  @override
  Widget build(BuildContext context) {
    if (images.isEmpty) {
      return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.image_outlined, size: 40, color: AriaTheme.textSubtle),
        const SizedBox(height: 12),
        Text('No images collected', style: AriaTheme.inter(size: 14, color: AriaTheme.textMuted)),
      ]));
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
        final img  = images[i];
        final url  = img['url'] as String? ?? '';
        final alt  = img['alt'] as String? ?? img['caption'] as String? ?? '';
        final src  = img['source'] as String? ?? '';

        return _ImageTile(url: url, alt: alt, source: src);
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
      child: GestureDetector(
        onTap: () {
          if (widget.url.isNotEmpty) {
            // Would open URL — skip for now
          }
        },
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
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topCenter, end: Alignment.bottomCenter,
                        colors: [Colors.transparent, Colors.black.withAlpha(180)],
                      ),
                    ),
                    child: Text(widget.alt,
                      style: AriaTheme.inter(size: 10, color: Colors.white),
                      maxLines: 2, overflow: TextOverflow.ellipsis),
                  ),
                ),
            ]),
          ),
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
            child: Text(alt, style: AriaTheme.inter(size: 9, color: AriaTheme.textSubtle),
              textAlign: TextAlign.center, maxLines: 2, overflow: TextOverflow.ellipsis),
          ),
        ],
      ])),
    );
  }
}
