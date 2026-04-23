import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../services/api_client.dart';

/// Connection state for credential-based sources and platforms.
enum ConnState { disconnected, checking, connected, failed }

// ─────────────────────────────────────────────
// Small data classes
// ─────────────────────────────────────────────

class EnsembleModelEntry {
  EnsembleModelEntry({
    required this.provider,
    required this.modelId,
    this.apiKey,
    this.baseUrl,
  });

  final String provider;
  final String modelId;
  final String? apiKey;
  final String? baseUrl;

  Map<String, dynamic> toJson() => {
    'provider': provider,
    'model_id': modelId,
    if (apiKey != null && apiKey!.isNotEmpty) 'api_key': apiKey,
    if (baseUrl != null && baseUrl!.isNotEmpty) 'base_url': baseUrl,
  };
}

class CloudProviderEntry {
  CloudProviderEntry({
    required this.apiKey,
    this.detectedProvider = '',
    this.detectedName = '',
    this.availableModels = const [],
    this.selectedModels = const [],
    this.baseUrl = '',
  });

  final String apiKey;
  final String detectedProvider;
  final String detectedName;
  final List<String> availableModels;
  final List<String> selectedModels;
  final String baseUrl;

  CloudProviderEntry copyWith({
    String? detectedProvider,
    String? detectedName,
    List<String>? availableModels,
    List<String>? selectedModels,
    String? baseUrl,
  }) => CloudProviderEntry(
    apiKey: apiKey,
    detectedProvider: detectedProvider ?? this.detectedProvider,
    detectedName: detectedName ?? this.detectedName,
    availableModels: availableModels ?? this.availableModels,
    selectedModels: selectedModels ?? this.selectedModels,
    baseUrl: baseUrl ?? this.baseUrl,
  );
}

class PlatformEntry {
  PlatformEntry({required this.id, required this.label, this.connected = false});

  final String id;
  final String label;
  final bool connected;

  PlatformEntry copyWith({bool? connected}) =>
      PlatformEntry(id: id, label: label, connected: connected ?? this.connected);
}

// ─────────────────────────────────────────────
// Controller
// ─────────────────────────────────────────────

class AriaController extends ChangeNotifier {
  final AriaApiClient _api = AriaApiClient();

  // ── Connection ──
  bool isConnected = false;
  bool isBusy = false;
  String apiBaseUrl = 'http://127.0.0.1:8765';
  static const _kApiUrl = 'aria_api_base_url';

  /// Load persisted settings. Called once at startup.
  Future<void> loadPersistedSettings() async {
    final prefs = await SharedPreferences.getInstance();
    final savedUrl = prefs.getString(_kApiUrl);
    if (savedUrl != null && savedUrl.isNotEmpty) {
      apiBaseUrl = savedUrl;
      _api.baseUrl = savedUrl;
    }
    notifyListeners();
  }

  Future<void> persistApiUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kApiUrl, url);
    updateApiBaseUrl(url);
  }

  // ── Search bar ──
  String topic = '';
  String intent = '';
  String lastValidationMessage = '';

  // ── Free sources ──
  bool srcWeb = true;
  bool srcPdf = true;
  bool srcAcademic = true;
  bool srcYoutube = false;
  bool srcReddit = false;
  bool srcHackernews = false;
  bool srcWikipedia = false;
  bool srcRss = false;
  bool srcStackoverflow = false;
  bool srcMedium = false;
  bool srcSubstack = false;
  bool srcDevto = false;

  // ── New collectors (previously fake, now real) ──
  bool srcGithub       = false;
  bool srcNews         = false;
  bool srcGovernment   = false;
  bool srcMultilingual = false;

  // ── Auth sources ──
  bool srcTwitter = false;
  bool srcLinkedin = false;
  bool srcNotion = false;
  bool srcSlack = false;
  bool srcPodcast = false;
  bool srcVimeo = false;
  bool srcZotero = false;

  // ── Auth tokens for new sources ──
  String twitterBearerToken = '';
  String linkedinEmail = '';
  String linkedinPassword = '';
  String notionToken = '';
  String slackToken = '';
  String vimeoToken = '';

  // ── Zotero config ──
  String zoteroMode = 'local';           // 'local' | 'cloud'
  String zoteroCollectionKey = '';       // empty = all items
  String zoteroLibraryId = '';           // required for cloud mode
  String zoteroApiKey = '';              // required for cloud mode
  String zoteroLibraryType = 'user';     // 'user' | 'group'

  // ── Depth level ──
  int depthLevel = 3; // 1-5

  // ── ARIA 5.0: Domain-based collection ──
  List<String> selectedDomains = [];   // e.g. ['health', 'finance']
  List<String> selectedCountries = []; // e.g. ['IN', 'US']
  int citationDepth = 0;               // 0-3 (0 = disabled)

  // ── ARIA 5.0: Methodology + run history ──
  List<Map<String, dynamic>> runHistory = [];
  Map<String, dynamic> runDetailResult = {};
  bool isAnalyzingIntent = false;
  Map<String, dynamic> intentSuggestions = {};

  // Run detail derived getters
  List<Map<String, dynamic>> get runDetailDocuments => List<Map<String, dynamic>>.from(
      runDetailResult['documents'] as List? ?? []);
  Map<String, dynamic> get runDetailKg =>
      Map<String, dynamic>.from(runDetailResult['knowledge_graph'] as Map? ?? {});
  List<Map<String, dynamic>> get runDetailGaps => List<Map<String, dynamic>>.from(
      runDetailResult['gaps'] as List? ?? []);
  List<Map<String, dynamic>> get runDetailImages => List<Map<String, dynamic>>.from(
      runDetailResult['images'] as List? ?? []);

  // ── Cleaning config ──
  // globalInstructions is now an optional manual override only.
  // Smart cleaning is driven automatically by the research intent/topic.
  String globalInstructions = '';
  Map<String, String> perSourceInstructions = {
    'web':          '',
    'pdf':          '',
    'academic':     '',
    'youtube':      '',
    'reddit':       '',
    'hackernews':   '',
    'wikipedia':    '',
    'stackoverflow':'',
    'medium':       '',
    'devto':        '',
    'twitter':      '',
    'linkedin':     '',
    'notion':       '',
    'slack':        '',
    'podcast':      '',
    'vimeo':        '',
    'rss':          '',
    'substack':     '',
    'zotero':       '',
    'github':       '',
    'news':         '',
    'government':   '',
    'multilingual': '',
  };
  String outputSchemaJson = '{\n  "is_relevant": "bool",\n  "relevance_score": "float",\n  "title": "string",\n  "summary": "string",\n  "key_topics": ["string"],\n  "entities": { "organizations": ["string"], "locations": ["string"], "people": ["string"] },\n  "quality_issues": ["string"]\n}';
  bool chunkingEnabled = false;
  int chunkSize = 8000;
  int chunkOverlap = 500;

  // ── LLM toggle ──
  bool useLlm = false;
  String llmMode = 'cloud'; // 'cloud' | 'local'

  // ── Cloud providers ──
  List<CloudProviderEntry> cloudProviders = [];
  String _pendingApiKey = '';
  bool isDetecting = false;

  // ── Local (Ollama) ──
  bool ollamaConnected = false;
  List<String> ollamaAvailableModels = [];
  List<String> ollamaSelectedModels = [];

  // ── Cleaning brain (system model — excluded from ensemble) ──
  Map<String, dynamic> cleaningBrain = {};

  // ── Auth source connection states ──
  final Map<String, ConnState> authSourceStates = {
    'twitter':  ConnState.disconnected,
    'linkedin': ConnState.disconnected,
    'notion':   ConnState.disconnected,
    'slack':    ConnState.disconnected,
    'vimeo':    ConnState.disconnected,
    'zotero':   ConnState.disconnected,
  };

  // ── Feed URLs for RSS / Podcast / Substack ──
  List<String> feedUrls = [];        // shared list used by all three
  String feedUrlsText = '';          // raw textarea content (newline-separated)

  // ── Subscription platforms ──
  List<PlatformEntry> platforms = [
    PlatformEntry(id: 'ieee', label: 'IEEE Xplore'),
    PlatformEntry(id: 'acm', label: 'ACM Digital Library'),
    PlatformEntry(id: 'springer', label: 'Springer'),
    PlatformEntry(id: 'elsevier', label: 'Elsevier / ScienceDirect'),
    PlatformEntry(id: 'jstor', label: 'JSTOR'),
    PlatformEntry(id: 'university_library', label: 'University Library'),
  ];

  // ── Run state ──
  String runId = '';
  String runStatus = 'idle';
  String runStage = 'idle';
  String runMessage = 'Waiting for a run';

  // ── Download state ──
  // Keys: 'raw_json', 'raw_csv', 'clean_json', 'clean_csv', 'clean_md', 'zip'
  final Map<String, bool>   _downloading = {};
  final Map<String, String> _downloadResults = {};

  bool   isDownloading(String key) => _downloading[key] ?? false;
  String downloadResult(String key) => _downloadResults[key] ?? '';

  // Legacy getters kept for backward compat with existing widget code
  bool get isDownloadingRaw   => isDownloading('raw_json');
  bool get isDownloadingClean => isDownloading('clean_json');
  String get rawDownloadResult   => downloadResult('raw_json');
  String get cleanDownloadResult => downloadResult('clean_json');
  List<Map<String, dynamic>> logs = [];
  Map<String, dynamic> stats = {};
  Map<String, dynamic> exports = {};
  List<Map<String, dynamic>> documents = [];
  List<Map<String, dynamic>> ensembleDocuments = [];

  // ── Intelligence state ──
  Map<String, dynamic> knowledgeGraph = {};
  Map<String, dynamic> gapAnalysis = {};
  Map<String, dynamic> methodology = {};
  List<Map<String, dynamic>> collectedImages = [];
  int contradictionsCount = 0;
  int gapsCount = 0;
  int imagesCount = 0;
  List<Map<String, dynamic>> topEntities = [];

  Timer? _poller;

  Future<void> bootstrap() async {
    await refreshConnection();
    if (isConnected) {
      await _loadCleaningBrain();
      await _loadPlatformStatus();
    }
  }

  Future<void> refreshConnection() async {
    _api.baseUrl = apiBaseUrl;
    try {
      isConnected = await _api.health();
      lastValidationMessage = isConnected ? 'API connected.' : 'API unreachable.';
    } catch (e) {
      isConnected = false;
      lastValidationMessage = 'API unreachable: $e';
    }
    notifyListeners();
  }

  Future<void> _loadCleaningBrain() async {
    if (!isConnected) return;
    try {
      final payload = await _api.llmSources();
      cleaningBrain = Map<String, dynamic>.from(
        payload['cleaning_brain'] as Map<String, dynamic>? ?? {},
      );
    } catch (_) {}
    notifyListeners();
  }

  Future<void> _loadPlatformStatus() async {
    if (!isConnected) return;
    try {
      final statuses = await _api.platformStatus();
      platforms = platforms.map((p) {
        final found = statuses.firstWhere(
          (s) => s['platform'] == p.id,
          orElse: () => {'platform': p.id, 'connected': false},
        );
        return p.copyWith(connected: found['connected'] == true);
      }).toList();
    } catch (_) {}
    notifyListeners();
  }

  // ── Search bar ──

  void updateTopic(String value) {
    topic = value;
    notifyListeners();
  }

  void updateIntent(String value) {
    intent = value;
    notifyListeners();
  }

  void updateApiBaseUrl(String value) {
    apiBaseUrl = value;
    notifyListeners();
  }

  // ── Free source toggles ──

  void toggleSrcWeb(bool v) { srcWeb = v; notifyListeners(); }
  void toggleSrcPdf(bool v) { srcPdf = v; notifyListeners(); }
  void toggleSrcAcademic(bool v) { srcAcademic = v; notifyListeners(); }
  void toggleSrcYoutube(bool v) { srcYoutube = v; notifyListeners(); }
  void toggleSrcReddit(bool v) { srcReddit = v; notifyListeners(); }
  void toggleSrcHackernews(bool v) { srcHackernews = v; notifyListeners(); }
  void toggleSrcWikipedia(bool v) { srcWikipedia = v; notifyListeners(); }
  void toggleSrcRss(bool v) { srcRss = v; notifyListeners(); }
  void toggleSrcStackoverflow(bool v) { srcStackoverflow = v; notifyListeners(); }
  void toggleSrcMedium(bool v) { srcMedium = v; notifyListeners(); }
  void toggleSrcSubstack(bool v) { srcSubstack = v; notifyListeners(); }
  void toggleSrcDevto(bool v)        { srcDevto        = v; notifyListeners(); }
  void toggleSrcGithub(bool v)      { srcGithub       = v; notifyListeners(); }
  void toggleSrcNews(bool v)        { srcNews         = v; notifyListeners(); }
  void toggleSrcGovernment(bool v)  { srcGovernment   = v; notifyListeners(); }
  void toggleSrcMultilingual(bool v){ srcMultilingual  = v; notifyListeners(); }
  void toggleSrcTwitter(bool v) { srcTwitter = v; notifyListeners(); }
  void toggleSrcLinkedin(bool v) { srcLinkedin = v; notifyListeners(); }
  void toggleSrcNotion(bool v) { srcNotion = v; notifyListeners(); }
  void toggleSrcSlack(bool v) { srcSlack = v; notifyListeners(); }
  void toggleSrcPodcast(bool v) { srcPodcast = v; notifyListeners(); }
  void toggleSrcVimeo(bool v) { srcVimeo = v; notifyListeners(); }
  void toggleSrcZotero(bool v) { srcZotero = v; notifyListeners(); }

  void updateZoteroMode(String v)          { zoteroMode = v; notifyListeners(); }
  void updateZoteroCollectionKey(String v) { zoteroCollectionKey = v; notifyListeners(); }
  void updateZoteroLibraryId(String v)     { zoteroLibraryId = v; notifyListeners(); }
  void updateZoteroApiKey(String v)        { zoteroApiKey = v; notifyListeners(); }
  void updateZoteroLibraryType(String v)   { zoteroLibraryType = v; notifyListeners(); }

  void updateDepthLevel(int v) { depthLevel = v.clamp(1, 5); notifyListeners(); }

  // ── Cleaning ──
  void updateGlobalInstructions(String v) { globalInstructions = v; notifyListeners(); }
  void updatePerSourceInstruction(String source, String v) {
    perSourceInstructions = Map.from(perSourceInstructions)..[source] = v;
    notifyListeners();
  }
  void updateOutputSchemaJson(String v) { outputSchemaJson = v; notifyListeners(); }
  void toggleChunking(bool v) { chunkingEnabled = v; notifyListeners(); }
  void updateChunkSize(int v) { chunkSize = v; notifyListeners(); }
  void updateChunkOverlap(int v) { chunkOverlap = v; notifyListeners(); }
  void updateTwitterToken(String v) { twitterBearerToken = v; notifyListeners(); }
  void updateLinkedinEmail(String v) { linkedinEmail = v; notifyListeners(); }
  void updateLinkedinPassword(String v) { linkedinPassword = v; notifyListeners(); }
  void updateNotionToken(String v) { notionToken = v; notifyListeners(); }
  void updateSlackToken(String v) { slackToken = v; notifyListeners(); }
  void updateVimeoToken(String v) { vimeoToken = v; notifyListeners(); }

  // ── LLM panel ──

  void toggleUseLlm(bool v) { useLlm = v; notifyListeners(); }
  void setLlmMode(String mode) { llmMode = mode; notifyListeners(); }

  // ── Cloud provider ──

  void updatePendingApiKey(String key) {
    _pendingApiKey = key;
    notifyListeners();
  }

  Future<void> detectProvider() async {
    if (_pendingApiKey.trim().isEmpty || !isConnected) return;
    isDetecting = true;
    notifyListeners();
    try {
      final result = await _api.detectProvider(_pendingApiKey.trim());
      final provider = CloudProviderEntry(
        apiKey: _pendingApiKey.trim(),
        detectedProvider: result['provider'] as String? ?? '',
        detectedName: result['name'] as String? ?? '',
        availableModels: List<String>.from(result['models'] as List? ?? []),
        selectedModels: [],
        baseUrl: result['base_url'] as String? ?? '',
      );
      cloudProviders = [...cloudProviders, provider];
      _pendingApiKey = '';
    } catch (e) {
      lastValidationMessage = 'Detection failed: $e';
    }
    isDetecting = false;
    notifyListeners();
  }

  void removeCloudProvider(int index) {
    cloudProviders = [...cloudProviders]..removeAt(index);
    notifyListeners();
  }

  void toggleCloudModel(int providerIndex, String modelId) {
    final p = cloudProviders[providerIndex];
    final selected = List<String>.from(p.selectedModels);
    if (selected.contains(modelId)) {
      selected.remove(modelId);
    } else {
      selected.add(modelId);
    }
    final updated = List<CloudProviderEntry>.from(cloudProviders);
    updated[providerIndex] = p.copyWith(selectedModels: selected);
    cloudProviders = updated;
    notifyListeners();
  }

  // ── Local / Ollama ──

  Future<void> detectOllama() async {
    if (!isConnected) return;
    isBusy = true;
    notifyListeners();
    try {
      final models = await _api.ollamaModels();
      ollamaConnected = models.isNotEmpty;
      ollamaAvailableModels = models;
    } catch (_) {
      ollamaConnected = false;
      ollamaAvailableModels = [];
    }
    isBusy = false;
    notifyListeners();
  }

  void toggleOllamaModel(String modelId) {
    final selected = List<String>.from(ollamaSelectedModels);
    if (selected.contains(modelId)) {
      selected.remove(modelId);
    } else {
      selected.add(modelId);
    }
    ollamaSelectedModels = selected;
    notifyListeners();
  }

  // ── Platforms ──

  Future<bool> loginPlatform(String platformId, String username, String password) async {
    if (!isConnected) return false;
    if (username.trim().isEmpty || password.trim().isEmpty) {
      lastValidationMessage = 'Username and password are required';
      notifyListeners();
      return false;
    }
    try {
      final result = await _api.platformLogin(platformId, username.trim(), password.trim());
      final success = result['connected'] == true || result['status'] == 'connected';
      if (success) {
        platforms = platforms.map((p) {
          if (p.id == platformId) return p.copyWith(connected: true);
          return p;
        }).toList();
      } else {
        lastValidationMessage = result['message'] as String? ?? 'Login failed — check credentials';
      }
      notifyListeners();
      return success;
    } catch (e) {
      lastValidationMessage = 'Login failed: $e';
      notifyListeners();
      return false;
    }
  }

  void disconnectPlatform(String platformId) {
    platforms = platforms.map((p) {
      if (p.id == platformId) return p.copyWith(connected: false);
      return p;
    }).toList();
    notifyListeners();
  }

  // ── Auth source connect ──

  Future<Map<String, dynamic>> connectSourceCredentials(String source, Map<String, String> creds) async {
    if (!isConnected) return {'connected': false, 'message': 'API not connected'};
    try {
      final payload = {'platform': source, ...creds};
      final response = await http.post(
        Uri.parse('$apiBaseUrl/api/platforms/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(payload),
      );
      return jsonDecode(response.body) as Map<String, dynamic>;
    } catch (e) {
      return {'connected': false, 'message': e.toString()};
    }
  }

  Future<void> connectAuthSource(String source, Map<String, String> credentials) async {
    if (!isConnected) return;
    authSourceStates[source] = ConnState.checking;
    notifyListeners();
    try {
      final result = await connectSourceCredentials(source, credentials);
      if (result['connected'] == true) {
        authSourceStates[source] = ConnState.connected;
        lastValidationMessage = result['message'] as String? ?? '$source connected';
      } else {
        authSourceStates[source] = ConnState.failed;
        lastValidationMessage = result['message'] as String? ?? '$source connection failed';
      }
    } catch (e) {
      authSourceStates[source] = ConnState.failed;
      lastValidationMessage = 'Connection error: $e';
    }
    notifyListeners();
  }

  void resetAuthSource(String source) {
    authSourceStates[source] = ConnState.disconnected;
    notifyListeners();
  }

  // ── Feed URLs ──
  void updateFeedUrlsText(String text) {
    feedUrlsText = text;
    feedUrls = text
        .split('\n')
        .map((u) => u.trim())
        .where((u) => u.isNotEmpty && (u.startsWith('http') || u.contains('.')))
        .toList();
    notifyListeners();
  }

  // ── Auth source validation for run ──
  List<String> get blockedAuthSources {
    final blocked = <String>[];
    if (srcTwitter  && authSourceStates['twitter']  != ConnState.connected) blocked.add('Twitter/X');
    if (srcLinkedin && authSourceStates['linkedin'] != ConnState.connected) blocked.add('LinkedIn');
    if (srcNotion   && authSourceStates['notion']   != ConnState.connected) blocked.add('Notion');
    if (srcSlack    && authSourceStates['slack']    != ConnState.connected) blocked.add('Slack');
    if (srcVimeo    && authSourceStates['vimeo']    != ConnState.connected) blocked.add('Vimeo');
    return blocked;
  }

  // ── Helpers ──

  String get cleaningBrainLabel {
    final provider = cleaningBrain['provider'] as String? ?? '';
    final model = cleaningBrain['model_id'] as String? ?? '';
    if (provider.isEmpty && model.isEmpty) return '';
    return '$provider / $model';
  }

  bool _isSystemModel(String provider, String modelId) {
    final brainProvider = cleaningBrain['provider'] as String? ?? '';
    final brainModel = cleaningBrain['model_id'] as String? ?? '';
    return provider == brainProvider && modelId == brainModel;
  }

  List<EnsembleModelEntry> get selectedEnsembleModels {
    final result = <EnsembleModelEntry>[];
    if (llmMode == 'cloud') {
      for (final cp in cloudProviders) {
        for (final modelId in cp.selectedModels) {
          if (!_isSystemModel(cp.detectedProvider, modelId)) {
            result.add(EnsembleModelEntry(
              provider: cp.detectedProvider,
              modelId: modelId,
              apiKey: cp.apiKey,
              baseUrl: cp.baseUrl.isNotEmpty ? cp.baseUrl : null,
            ));
          }
        }
      }
    } else {
      for (final modelId in ollamaSelectedModels) {
        if (!_isSystemModel('ollama', modelId)) {
          result.add(EnsembleModelEntry(provider: 'ollama', modelId: modelId));
        }
      }
    }
    return result;
  }

  // ── Run ──

  Future<void> startRun() async {
    if (!isConnected || topic.trim().isEmpty) return;
    isBusy = true;
    notifyListeners();
    try {
      final payload = {
        'topic': topic.trim(),
        'intent': intent.trim().isNotEmpty ? intent.trim() : topic.trim(),
        'depth_level': depthLevel,
        'free_sources': {
          'web': srcWeb,
          'pdf': srcPdf,
          'academic': srcAcademic,
          'youtube': srcYoutube,
          'reddit': srcReddit,
          'hackernews': srcHackernews,
          'wikipedia': srcWikipedia,
          'rss': srcRss,
          'stackoverflow': srcStackoverflow,
          'medium': srcMedium,
          'substack': srcSubstack,
          'devto': srcDevto,
          'github': srcGithub,
          'news': srcNews,
          'government': srcGovernment,
          'multilingual': srcMultilingual,
        },
        'auth_sources': {
          'twitter': srcTwitter,
          'linkedin': srcLinkedin,
          'notion': srcNotion,
          'slack': srcSlack,
          'podcast': srcPodcast,
          'vimeo': srcVimeo,
          'zotero': srcZotero,
        },
        'auth_tokens': {
          if (twitterBearerToken.isNotEmpty) 'twitter_bearer_token': twitterBearerToken,
          if (linkedinEmail.isNotEmpty) 'linkedin_email': linkedinEmail,
          if (linkedinPassword.isNotEmpty) 'linkedin_password': linkedinPassword,
          if (notionToken.isNotEmpty) 'notion_token': notionToken,
          if (slackToken.isNotEmpty) 'slack_token': slackToken,
          if (vimeoToken.isNotEmpty) 'vimeo_token': vimeoToken,
        },
        if (feedUrls.isNotEmpty) 'feed_urls': feedUrls,
        if (srcZotero) 'zotero_config': {
          'mode':           zoteroMode,
          'collection_key': zoteroCollectionKey,
          'library_id':     zoteroLibraryId,
          'api_key':        zoteroApiKey,
          'library_type':   zoteroLibraryType,
        },
        'cleaning': {
          // research_goal drives smart automatic cleaning —
          // the LLM detects content type and applies the right extraction strategy.
          'research_goal': intent.trim().isNotEmpty ? intent.trim() : topic.trim(),
          // instructions is an optional manual override; leave empty to use smart mode.
          if (globalInstructions.trim().isNotEmpty)
            'instructions': globalInstructions.trim(),
          'per_source': Map.fromEntries(
            perSourceInstructions.entries.where((e) => e.value.trim().isNotEmpty),
          ),
          'output_schema': _parseSchemaJson(outputSchemaJson),
          'chunking': {
            'enabled': chunkingEnabled,
            'chunk_size': chunkSize,
            'overlap': chunkOverlap,
          },
        },
        'ensemble_models': useLlm
            ? selectedEnsembleModels.map((m) => m.toJson()).toList()
            : [],
        // ARIA 5.0 domain params
        if (selectedDomains.isNotEmpty) 'domains': selectedDomains,
        if (selectedCountries.isNotEmpty) 'countries': selectedCountries,
        if (citationDepth > 0) 'citation_depth': citationDepth,
        'flags': {
          'collect_only': false,
          'clean_only': false,
          'resume': false,
          'authenticated_only': false,
          'public_only': false,
        },
      };
      final result = await _api.startRun(payload);
      runId = result['run_id'] as String? ?? '';
      runStatus = result['status'] as String? ?? 'queued';
      runStage = 'queued';
      runMessage = 'Run queued';
      logs = [];
      stats = {};
      exports = {};
      documents = [];
      ensembleDocuments = [];
      _startPolling();
    } catch (e) {
      lastValidationMessage = 'Failed to start run: $e';
    }
    isBusy = false;
    notifyListeners();
  }

  // ── Downloads ──

  Future<void> saveRawJson()      => _downloadJson('raw_json',   () => _api.exportRaw(runId),          'aria_raw_$runId.json');
  Future<void> saveRawCsv()       => _downloadBytes('raw_csv',   () => _api.exportRawCsv(runId),       'aria_raw_$runId.csv');
  Future<void> saveCleanJson()    => _downloadJson('clean_json', () => _api.exportClean(runId),         'aria_clean_$runId.json');
  Future<void> saveCleanCsv()     => _downloadBytes('clean_csv', () => _api.exportCleanCsv(runId),     'aria_clean_$runId.csv');
  Future<void> saveCleanMarkdown()=> _downloadBytes('clean_md',  () => _api.exportCleanMarkdown(runId),'aria_clean_$runId.md');
  Future<void> saveZip()          => _downloadBytes('zip',       () => _api.exportZip(runId),          'aria_export_$runId.zip');

  // Legacy wrappers so old callsites still compile
  Future<void> saveRawData()   => saveRawJson();
  Future<void> saveCleanData() => saveCleanJson();

  Future<void> _downloadJson(
    String key,
    Future<Map<String, dynamic>> Function() fetch,
    String filename,
  ) async {
    if (runId.isEmpty) {
      _downloadResults[key] = 'Error: No active run — launch a run first';
      notifyListeners();
      return;
    }
    if (!isConnected) {
      _downloadResults[key] = 'Error: API not connected';
      notifyListeners();
      return;
    }
    _downloading[key] = true;
    _downloadResults.remove(key);
    notifyListeners();
    try {
      final data = await fetch();
      final path = await _writeToDisk(
        const JsonEncoder.withIndent('  ').convert(data).codeUnits,
        filename,
      );
      _downloadResults[key] = path;
    } catch (e) {
      _downloadResults[key] = 'Error: $e';
    }
    _downloading[key] = false;
    notifyListeners();
  }

  Future<void> _downloadBytes(
    String key,
    Future<List<int>> Function() fetch,
    String filename,
  ) async {
    if (runId.isEmpty) {
      _downloadResults[key] = 'Error: No active run — launch a run first';
      notifyListeners();
      return;
    }
    if (!isConnected) {
      _downloadResults[key] = 'Error: API not connected';
      notifyListeners();
      return;
    }
    _downloading[key] = true;
    _downloadResults.remove(key);
    notifyListeners();
    try {
      final bytes = await fetch();
      final path = await _writeToDisk(bytes, filename);
      _downloadResults[key] = path;
    } catch (e) {
      _downloadResults[key] = 'Error: $e';
    }
    _downloading[key] = false;
    notifyListeners();
  }

  /// Write [bytes] to ~/Downloads/[filename]. Returns the saved path.
  Future<String> _writeToDisk(List<int> bytes, String filename) async {
    final home = Platform.environment['HOME'] ??
        Platform.environment['USERPROFILE'] ??
        '.';
    final downloads = Directory('$home/Downloads');
    final dir = downloads.existsSync() ? downloads : Directory(home);
    final file = File('${dir.path}/$filename');
    await file.writeAsBytes(bytes);
    return file.path;
  }

  void _startPolling() {
    _poller?.cancel();
    _poller = Timer.periodic(const Duration(seconds: 2), (_) => _pollRun());
  }

  Future<void> _pollRun() async {
    if (runId.isEmpty || !isConnected) return;
    try {
      final result = await _api.getRun(runId);
      runStatus = result['status'] as String? ?? runStatus;
      runStage = result['stage'] as String? ?? runStage;
      runMessage = result['message'] as String? ?? runMessage;
      logs = List<Map<String, dynamic>>.from(result['logs'] as List? ?? []);
      stats = Map<String, dynamic>.from(result['stats'] as Map? ?? {});
      exports = Map<String, dynamic>.from(result['exports'] as Map? ?? {});
      documents = List<Map<String, dynamic>>.from(result['documents'] as List? ?? []);
      ensembleDocuments = List<Map<String, dynamic>>.from(
        result['ensemble_documents'] as List? ?? [],
      );
      // Intelligence outputs from run status
      contradictionsCount = (result['contradictions_count'] as num? ?? 0).toInt();
      gapsCount = (result['gaps_count'] as num? ?? 0).toInt();
      imagesCount = (result['images_count'] as num? ?? 0).toInt();
      topEntities = List<Map<String, dynamic>>.from(result['top_entities'] as List? ?? []);
      methodology = Map<String, dynamic>.from(result['methodology'] as Map? ?? {});

      if (runStatus == 'completed' || runStatus == 'failed') {
        _poller?.cancel();
        // Fetch full intelligence data on completion
        _fetchIntelligenceData();
      }
    } catch (e) {
      runMessage = 'Poll error: $e';
    }
    notifyListeners();
  }

  Future<void> _fetchIntelligenceData() async {
    if (runId.isEmpty || !isConnected) return;
    try {
      final results = await Future.wait([
        _api.getKnowledgeGraph(runId),
        _api.getGapAnalysis(runId),
        _api.getImages(runId),
      ]);
      knowledgeGraph = results[0] as Map<String, dynamic>;
      gapAnalysis    = results[1] as Map<String, dynamic>;
      collectedImages = results[2] as List<Map<String, dynamic>>;
    } catch (_) {}
    notifyListeners();
  }

  Map<String, dynamic> _parseSchemaJson(String raw) {
    try {
      final decoded = jsonDecode(raw);
      if (decoded is Map<String, dynamic>) return decoded;
    } catch (_) {}
    return {
      'is_relevant': 'bool',
      'relevance_score': 'float',
      'title': 'string',
      'summary': 'string',
    };
  }

  // ── ARIA 5.0 methods ──

  void toggleDomain(String domain) {
    final list = List<String>.from(selectedDomains);
    if (list.contains(domain)) { list.remove(domain); } else { list.add(domain); }
    selectedDomains = list;
    notifyListeners();
  }

  void toggleCountry(String country) {
    final list = List<String>.from(selectedCountries);
    if (list.contains(country)) { list.remove(country); } else { list.add(country); }
    selectedCountries = list;
    notifyListeners();
  }

  void updateCitationDepth(int v) { citationDepth = v.clamp(0, 3); notifyListeners(); }

  Future<void> runIntentAnalysis() async {
    if (!isConnected || topic.trim().isEmpty) return;
    isAnalyzingIntent = true;
    notifyListeners();
    try {
      final result = await _api.analyzeIntent(topic.trim(), intent.trim());
      intentSuggestions = result;
      // Auto-select suggested domains if empty
      final suggestedDomains = List<String>.from(result['suggested_domains'] as List? ?? []);
      final suggestedCountries = List<String>.from(result['suggested_countries'] as List? ?? []);
      if (selectedDomains.isEmpty && suggestedDomains.isNotEmpty) {
        selectedDomains = suggestedDomains.take(3).toList();
      }
      if (selectedCountries.isEmpty && suggestedCountries.isNotEmpty) {
        selectedCountries = suggestedCountries.take(5).toList();
      }
    } catch (_) {}
    isAnalyzingIntent = false;
    notifyListeners();
  }

  Future<void> loadRunHistory() async {
    if (!isConnected) return;
    try {
      runHistory = await _api.listRuns();
    } catch (_) {}
    notifyListeners();
  }

  Future<void> loadRunDetail(String runId) async {
    if (!isConnected || runId.isEmpty) return;
    try {
      final result = await _api.getRun(runId);
      runDetailResult = Map<String, dynamic>.from(result);
      // Also fetch full intelligence data
      final kg = await _api.getKnowledgeGraph(runId);
      final ga = await _api.getGapAnalysis(runId);
      final imgs = await _api.getImages(runId);
      runDetailResult['knowledge_graph'] = kg;
      runDetailResult['gaps'] = (ga['gaps'] as List?) ?? [];
      runDetailResult['images'] = imgs;
    } catch (_) {}
    notifyListeners();
  }

  Future<void> downloadRunExport(String runId, String format) async {
    if (!isConnected || runId.isEmpty) return;
    _downloading[format] = true;
    _downloadResults.remove(format);
    notifyListeners();
    try {
      List<int> bytes;
      String filename;
      switch (format) {
        case 'raw_json':
          final data = await _api.exportRaw(runId);
          bytes = const JsonEncoder.withIndent('  ').convert(data).codeUnits;
          filename = 'aria_raw_$runId.json';
          break;
        case 'clean_json':
          final data = await _api.exportClean(runId);
          bytes = const JsonEncoder.withIndent('  ').convert(data).codeUnits;
          filename = 'aria_clean_$runId.json';
          break;
        case 'clean_csv':
          bytes = await _api.exportCleanCsv(runId);
          filename = 'aria_clean_$runId.csv';
          break;
        case 'clean_md':
          bytes = await _api.exportCleanMarkdown(runId);
          filename = 'aria_clean_$runId.md';
          break;
        case 'zip':
          bytes = await _api.exportZip(runId);
          filename = 'aria_export_$runId.zip';
          break;
        default:
          throw Exception('Unknown format: $format');
      }
      final path = await _writeToDisk(bytes, filename);
      _downloadResults[format] = path;
    } catch (e) {
      _downloadResults[format] = 'Error: $e';
    }
    _downloading[format] = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _poller?.cancel();
    super.dispose();
  }
}
