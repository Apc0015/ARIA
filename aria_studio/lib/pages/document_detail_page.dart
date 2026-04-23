// ARIA Studio — Document Detail Page
// Full-screen expanded view of a single document

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../theme/aria_theme.dart';
import '../widgets/effects_3d.dart';

class DocumentDetailPage extends StatelessWidget {
  const DocumentDetailPage({super.key, required this.doc});
  final Map<String, dynamic> doc;

  @override
  Widget build(BuildContext context) {
    final title    = doc['title'] as String? ?? 'Untitled';
    final url      = doc['url'] as String? ?? '';
    final summary  = doc['summary'] as String? ?? '';
    final fullText = doc['text'] as String? ?? doc['content'] as String? ?? '';
    final score    = (doc['relevance_score'] as num?)?.toStringAsFixed(3) ?? '';
    final source   = doc['source_type'] as String? ?? doc['platform'] as String? ?? '';
    final ctype    = doc['content_type'] as String? ?? doc['type'] as String? ?? '';
    final authors  = doc['authors'] as List? ?? [];
    final published = doc['published_date'] as String? ?? doc['published'] as String? ?? '';
    final lang     = doc['language'] as String? ?? doc['lang'] as String? ?? '';
    final wordCount = (doc['word_count'] as int?) ?? (doc['wordCount'] as int?) ?? 0;

    // Entities
    final entities = doc['entities'] as Map<String, dynamic>? ?? {};
    final orgs = List<String>.from(entities['organizations'] as List? ?? []);
    final people = List<String>.from(entities['people'] as List? ?? []);
    final locations = List<String>.from(entities['locations'] as List? ?? []);
    final topics = List<String>.from(doc['key_topics'] as List? ?? doc['topics'] as List? ?? []);

    // Quality
    final qualityIssues = List<String>.from(doc['quality_issues'] as List? ?? []);

    return Scaffold(
      backgroundColor: const Color(0xCC08090A),
      body: Stack(children: [
        // Subtle backdrop blur
        Positioned.fill(
          child: GestureDetector(
            onTap: () => Navigator.of(context).pop(),
            child: Container(color: Colors.transparent),
          ),
        ),
        // Modal card
        Center(
          child: Container(
            width: 680,
            constraints: BoxConstraints(
              maxHeight: MediaQuery.of(context).size.height * 0.88,
            ),
            decoration: BoxDecoration(
              color: AriaTheme.bg1,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AriaTheme.borderStandard),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withAlpha(80),
                  blurRadius: 40,
                  offset: const Offset(0, 20),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Header bar
                _DocHeader(
                  title: title, url: url, score: score,
                  source: source, ctype: ctype,
                  onClose: () => Navigator.of(context).pop(),
                ),
                // Scrollable body
                Flexible(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Metadata chips row
                        Wrap(
                          spacing: 6, runSpacing: 6,
                          children: [
                            if (source.isNotEmpty) _MetaChip(icon: Icons.source_outlined, label: source),
                            if (ctype.isNotEmpty) _MetaChip(icon: Icons.category_outlined, label: ctype),
                            if (lang.isNotEmpty) _MetaChip(icon: Icons.language_outlined, label: lang),
                            if (wordCount > 0) _MetaChip(icon: Icons.text_fields_outlined, label: '$wordCount words'),
                            if (published.isNotEmpty) _MetaChip(icon: Icons.calendar_today_outlined, label: _formatDate(published)),
                            if (score.isNotEmpty) _ScoreChip(score: score),
                          ],
                        ),
                        const SizedBox(height: 20),

                        // Authors
                        if (authors.isNotEmpty) ...[
                          Text('Authors', style: AriaTheme.inter(
                            size: 10, weight: FontWeight.w600,
                            color: AriaTheme.textSubtle, letterSpacing: 0.8)),
                          const SizedBox(height: 6),
                          Wrap(
                            spacing: 6, runSpacing: 6,
                            children: authors.map((a) => _AuthorChip(name: a.toString())).toList(),
                          ),
                          const SizedBox(height: 20),
                        ],

                        // Summary
                        if (summary.isNotEmpty) ...[
                          Text('Summary'.toUpperCase(), style: AriaTheme.inter(
                            size: 10, weight: FontWeight.w600,
                            color: AriaTheme.textSubtle, letterSpacing: 0.8)),
                          const SizedBox(height: 8),
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: const Color(0x08FFFFFF),
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: AriaTheme.borderSubtle),
                            ),
                            child: SelectableText(summary,
                              style: AriaTheme.inter(size: 13, color: AriaTheme.textSecondary, height: 1.7)),
                          ),
                          const SizedBox(height: 20),
                        ],

                        // Key topics
                        if (topics.isNotEmpty) ...[
                          Text('Key Topics'.toUpperCase(), style: AriaTheme.inter(
                            size: 10, weight: FontWeight.w600,
                            color: AriaTheme.textSubtle, letterSpacing: 0.8)),
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 6, runSpacing: 6,
                            children: topics.map((t) => _TopicChip(topic: t.toString())).toList(),
                          ),
                          const SizedBox(height: 20),
                        ],

                        // Entities
                        if (orgs.isNotEmpty || people.isNotEmpty || locations.isNotEmpty) ...[
                          Text('Named Entities'.toUpperCase(), style: AriaTheme.inter(
                            size: 10, weight: FontWeight.w600,
                            color: AriaTheme.textSubtle, letterSpacing: 0.8)),
                          const SizedBox(height: 8),
                          if (orgs.isNotEmpty) _EntityGroup(label: 'Organizations', items: orgs, color: AriaTheme.brandIndigo),
                          if (people.isNotEmpty) _EntityGroup(label: 'People', items: people, color: AriaTheme.accentViolet),
                          if (locations.isNotEmpty) _EntityGroup(label: 'Locations', items: locations, color: AriaTheme.statusEmerald),
                          const SizedBox(height: 20),
                        ],

                        // Quality issues
                        if (qualityIssues.isNotEmpty) ...[
                          Text('Quality Notes'.toUpperCase(), style: AriaTheme.inter(
                            size: 10, weight: FontWeight.w600,
                            color: AriaTheme.textSubtle, letterSpacing: 0.8)),
                          const SizedBox(height: 8),
                          ...qualityIssues.map((q) => Padding(
                            padding: const EdgeInsets.only(bottom: 6),
                            child: Row(children: [
                              const Icon(Icons.warning_amber_outlined, size: 13, color: AriaTheme.statusAmber),
                              const SizedBox(width: 8),
                              Expanded(child: Text(q,
                                style: AriaTheme.inter(size: 12, color: AriaTheme.textMuted, height: 1.5))),
                            ]),
                          )),
                          const SizedBox(height: 16),
                        ],

                        // Full text
                        if (fullText.isNotEmpty && fullText != summary) ...[
                          Text('Full Text'.toUpperCase(), style: AriaTheme.inter(
                            size: 10, weight: FontWeight.w600,
                            color: AriaTheme.textSubtle, letterSpacing: 0.8)),
                          const SizedBox(height: 8),
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: const Color(0x05FFFFFF),
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: AriaTheme.borderSubtle),
                            ),
                            constraints: const BoxConstraints(maxHeight: 400),
                            child: SingleChildScrollView(
                              child: SelectableText(fullText,
                                style: AriaTheme.inter(size: 12, color: AriaTheme.textMuted, height: 1.7)),
                            ),
                          ),
                          const SizedBox(height: 16),
                        ],

                        // URL
                        if (url.isNotEmpty) ...[
                          const Divider(color: AriaTheme.borderSubtle),
                          const SizedBox(height: 12),
                          Row(children: [
                            const Icon(Icons.link, size: 13, color: AriaTheme.textSubtle),
                            const SizedBox(width: 8),
                            Expanded(
                              child: SelectableText(url,
                                style: AriaTheme.inter(size: 11, color: AriaTheme.brandIndigo)),
                            ),
                            _CopyBtn(text: url),
                            const SizedBox(width: 6),
                            if (Uri.tryParse(url)?.hasAbsolutePath ?? false)
                              _OpenUrlBtn(url: url),
                          ]),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ]),
    );
  }

  String _formatDate(String d) {
    if (d.length > 10) return d.substring(0, 10);
    return d;
  }
}

class _DocHeader extends StatelessWidget {
  const _DocHeader({
    required this.title, required this.url, required this.score,
    required this.source, required this.ctype, required this.onClose,
  });
  final String title, url, score, source, ctype;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 14, 12, 14),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AriaTheme.borderSubtle)),
      ),
      child: Row(children: [
        const Icon(Icons.article_outlined, size: 16, color: AriaTheme.brandIndigo),
        const SizedBox(width: 10),
        Expanded(
          child: Text(title,
            style: AriaTheme.inter(size: 14, weight: FontWeight.w500, color: AriaTheme.textPrimary),
            maxLines: 1, overflow: TextOverflow.ellipsis),
        ),
        const SizedBox(width: 8),
        if (url.isNotEmpty) ...[
          IconButton(
            icon: const Icon(Icons.open_in_browser, size: 14),
            color: AriaTheme.textMuted,
            tooltip: 'Open URL',
            onPressed: () => _tryLaunch(url),
            visualDensity: VisualDensity.compact,
          ),
        ],
        IconButton(
          icon: const Icon(Icons.close, size: 16),
          color: AriaTheme.textMuted,
          onPressed: onClose,
          visualDensity: VisualDensity.compact,
        ),
      ]),
    );
  }

  Future<void> _tryLaunch(String url) async {
    final uri = Uri.tryParse(url);
    if (uri != null && await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }
}

class _MetaChip extends StatelessWidget {
  const _MetaChip({required this.icon, required this.label});
  final IconData icon;
  final String label;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: const Color(0x0AFFFFFF),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: AriaTheme.borderStandard),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 11, color: AriaTheme.textSubtle),
        const SizedBox(width: 5),
        Text(label, style: AriaTheme.inter(size: 11, color: AriaTheme.textMuted)),
      ]),
    );
  }
}

class _ScoreChip extends StatelessWidget {
  const _ScoreChip({required this.score});
  final String score;

  @override
  Widget build(BuildContext context) {
    final s = double.tryParse(score) ?? 0;
    final color = s >= 0.8 ? AriaTheme.statusEmerald
        : s >= 0.5 ? AriaTheme.statusAmber
        : AriaTheme.textMuted;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withAlpha(15),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withAlpha(40)),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.star_outline, size: 11, color: AriaTheme.statusAmber),
        const SizedBox(width: 5),
        Text('Relevance $score', style: AriaTheme.inter(size: 11, color: color)),
      ]),
    );
  }
}

class _AuthorChip extends StatelessWidget {
  const _AuthorChip({required this.name});
  final String name;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AriaTheme.accentViolet.withAlpha(10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AriaTheme.accentViolet.withAlpha(30)),
      ),
      child: Text(name, style: AriaTheme.inter(size: 11, color: AriaTheme.accentViolet)),
    );
  }
}

class _TopicChip extends StatelessWidget {
  const _TopicChip({required this.topic});
  final String topic;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AriaTheme.brandIndigo.withAlpha(10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AriaTheme.brandIndigo.withAlpha(30)),
      ),
      child: Text(topic, style: AriaTheme.inter(size: 11, color: AriaTheme.brandIndigo)),
    );
  }
}

class _EntityGroup extends StatelessWidget {
  const _EntityGroup({required this.label, required this.items, required this.color});
  final String label;
  final List<String> items;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: AriaTheme.inter(
            size: 11, color: color, weight: FontWeight.w500)),
          const SizedBox(height: 6),
          Wrap(
            spacing: 5, runSpacing: 5,
            children: items.take(15).map((item) => Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: color.withAlpha(10),
                borderRadius: BorderRadius.circular(4),
                border: Border.all(color: color.withAlpha(30)),
              ),
              child: Text(item, style: AriaTheme.inter(size: 11, color: AriaTheme.textMuted)),
            )).toList(),
          ),
        ],
      ),
    );
  }
}

class _CopyBtn extends StatefulWidget {
  const _CopyBtn({required this.text});
  final String text;
  @override
  State<_CopyBtn> createState() => _CopyBtnState();
}

class _CopyBtnState extends State<_CopyBtn> {
  bool _done = false;
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () async {
        await Clipboard.setData(ClipboardData(text: widget.text));
        setState(() => _done = true);
        await Future.delayed(const Duration(seconds: 1));
        if (mounted) setState(() => _done = false);
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: const Color(0x0AFFFFFF),
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: AriaTheme.borderStandard),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(_done ? Icons.check : Icons.copy, size: 11,
            color: _done ? AriaTheme.statusEmerald : AriaTheme.textMuted),
          const SizedBox(width: 4),
          Text(_done ? 'Copied' : 'Copy',
            style: AriaTheme.inter(size: 10, color: _done ? AriaTheme.statusEmerald : AriaTheme.textMuted)),
        ]),
      ),
    );
  }
}

class _OpenUrlBtn extends StatelessWidget {
  const _OpenUrlBtn({required this.url});
  final String url;
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () async {
        final uri = Uri.tryParse(url);
        if (uri != null && await canLaunchUrl(uri)) {
          await launchUrl(uri, mode: LaunchMode.externalApplication);
        }
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: AriaTheme.brandIndigo.withAlpha(15),
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: AriaTheme.brandIndigo.withAlpha(40)),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.open_in_new, size: 11, color: AriaTheme.brandIndigo),
          const SizedBox(width: 4),
          Text('Open', style: AriaTheme.inter(size: 10, color: AriaTheme.brandIndigo)),
        ]),
      ),
    );
  }
}
