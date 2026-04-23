// ARIA Studio — History Page
// Shows past research runs with status, topic, document count

import 'dart:math';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/aria_controller.dart';
import '../theme/aria_theme.dart';
import '../widgets/effects_3d.dart';
import '../widgets/shared.dart';

class HistoryPage extends StatefulWidget {
  const HistoryPage({super.key});
  @override
  State<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends State<HistoryPage> {
  bool _loading = false;
  int _displayCount = 20;
  static const _pageSize = 20;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    await context.read<AriaController>().loadRunHistory();
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final c = context.watch<AriaController>();
    return Scaffold(
      backgroundColor: AriaTheme.bg0,
      body: Stack(children: [
        const Positioned.fill(child: Opacity(opacity: 0.2, child: Aria3dStarField())),
        Column(children: [
          // Top bar
          Container(
            height: 52,
            decoration: const BoxDecoration(
              color: Color(0x80080A0F),
              border: Border(bottom: BorderSide(color: AriaTheme.borderSubtle)),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(children: [
              GestureDetector(
                onTap: () => Navigator.of(context).pop(),
                child: const Icon(Icons.arrow_back, size: 16, color: AriaTheme.textMuted),
              ),
              const SizedBox(width: 12),
              Text('ARIA', style: AriaTheme.inter(size: 18, weight: FontWeight.w700,
                  color: AriaTheme.brandIndigo, letterSpacing: 2.5)),
              Text(' / Run History', style: AriaTheme.inter(size: 14, color: AriaTheme.textMuted)),
              const Spacer(),
              GestureDetector(
                onTap: _load,
                child: const Icon(Icons.refresh, size: 16, color: AriaTheme.textMuted),
              ),
            ]),
          ),
          // Body
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator(color: AriaTheme.brandIndigo, strokeWidth: 1.5))
                : c.runHistory.isEmpty
                    ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                        const Icon(Icons.history, size: 32, color: AriaTheme.textSubtle),
                        const SizedBox(height: 12),
                        Text('No past runs', style: AriaTheme.inter(size: 15, color: AriaTheme.textMuted)),
                        const SizedBox(height: 6),
                        Text('Start a research run from the dashboard',
                            style: AriaTheme.inter(size: 13, color: AriaTheme.textSubtle)),
                      ]))
                    : ListView.builder(
                        padding: const EdgeInsets.all(20),
                        itemCount: min(_displayCount, c.runHistory.length) +
                            (c.runHistory.length > _displayCount ? 1 : 0),
                        itemBuilder: (ctx, i) {
                          if (i >= min(_displayCount, c.runHistory.length)) {
                            return Padding(
                              padding: const EdgeInsets.all(16),
                              child: AriaGhostButton(
                                label: 'Load ${min(_pageSize, c.runHistory.length - _displayCount)} more runs',
                                onPressed: () => setState(() => _displayCount += _pageSize),
                              ),
                            );
                          }
                          final run = c.runHistory[c.runHistory.length - 1 - i];
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: _RunHistoryCard(run: run, onTap: () {
                              final id = run['run_id'] as String? ?? run['id'] as String? ?? '';
                              if (id.isNotEmpty) {
                                Navigator.of(context).pushNamed('/reports', arguments: id);
                              }
                            }),
                          );
                        },
                      ),
          ),
        ]),
      ]),
    );
  }
}

class _RunHistoryCard extends StatefulWidget {
  const _RunHistoryCard({required this.run, required this.onTap});
  final Map<String, dynamic> run;
  final VoidCallback onTap;
  @override
  State<_RunHistoryCard> createState() => _RunHistoryCardState();
}

class _RunHistoryCardState extends State<_RunHistoryCard> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final run    = widget.run;
    final id     = run['run_id'] as String? ?? run['id'] as String? ?? '';
    final topic  = run['topic'] as String? ?? run['mission_name'] as String? ?? 'Untitled';
    final status = run['status'] as String? ?? 'unknown';
    final docs   = run['documents_collected'] as int? ?? run['total_documents'] as int? ?? 0;
    final ts     = run['created_at'] as String? ?? run['started_at'] as String? ?? '';
    final dur    = run['duration_seconds'] as num?;

    Color statusColor;
    IconData statusIcon;
    switch (status) {
      case 'completed': statusColor = AriaTheme.statusEmerald; statusIcon = Icons.check_circle_outline; break;
      case 'failed':    statusColor = AriaTheme.statusRed;     statusIcon = Icons.error_outline;         break;
      case 'running':   statusColor = AriaTheme.accentViolet;  statusIcon = Icons.pending_outlined;      break;
      default:          statusColor = AriaTheme.textSubtle;    statusIcon = Icons.radio_button_unchecked;
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
        child: Row(children: [
          Icon(statusIcon, size: 15, color: statusColor),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(topic.length > 80 ? '${topic.substring(0, 77)}…' : topic,
                style: AriaTheme.inter(size: 13, weight: FontWeight.w500, color: AriaTheme.textSecondary)),
            const SizedBox(height: 3),
            Row(children: [
              if (id.isNotEmpty) ...[
                Text('Run ${id.length > 8 ? id.substring(0, 8) : id}',
                    style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
                const SizedBox(width: 8),
                Container(width: 2, height: 2, decoration: const BoxDecoration(shape: BoxShape.circle, color: AriaTheme.textSubtle)),
                const SizedBox(width: 8),
              ],
              if (ts.isNotEmpty) ...[
                Text(ts.length > 19 ? ts.substring(0, 19).replaceAll('T', ' ') : ts,
                    style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
                const SizedBox(width: 8),
                Container(width: 2, height: 2, decoration: const BoxDecoration(shape: BoxShape.circle, color: AriaTheme.textSubtle)),
                const SizedBox(width: 8),
              ],
              if (dur != null)
                Text('${dur.toStringAsFixed(0)}s', style: AriaTheme.inter(size: 11, color: AriaTheme.textSubtle)),
            ]),
          ])),
          const SizedBox(width: 12),
          if (docs > 0) ...[
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text('$docs', style: AriaTheme.inter(size: 16, weight: FontWeight.w500, color: AriaTheme.textPrimary)),
              Text('docs', style: AriaTheme.inter(size: 10, color: AriaTheme.textSubtle)),
            ]),
            const SizedBox(width: 12),
          ],
          AriaPill(label: status, color: statusColor),
        ]),
      ),
      ),
    );
  }
}
