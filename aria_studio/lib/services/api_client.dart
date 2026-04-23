import 'dart:convert';

import 'package:http/http.dart' as http;

class AriaApiClient {
  AriaApiClient({String? baseUrl})
    : _baseUrl = baseUrl ?? 'http://127.0.0.1:8765';

  String _baseUrl;

  set baseUrl(String value) => _baseUrl = value;

  Future<bool> health() async {
    final response = await http.get(Uri.parse('$_baseUrl/api/health'));
    return response.statusCode == 200;
  }

  Future<Map<String, dynamic>> llmSources() async {
    final response = await http.get(Uri.parse('$_baseUrl/api/llm-sources'));
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> generateMission(Map<String, dynamic> payload) async {
    final response = await http.post(
      Uri.parse('$_baseUrl/api/mission/generate'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> validateMission(String missionYaml) async {
    final response = await http.post(
      Uri.parse('$_baseUrl/api/mission/validate'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'mission_yaml': missionYaml}),
    );
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> detectProvider(String apiKey) async {
    final response = await http.post(
      Uri.parse('$_baseUrl/api/llm/detect'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'api_key': apiKey}),
    );
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<List<String>> ollamaModels() async {
    final response = await http.get(Uri.parse('$_baseUrl/api/llm/ollama/models'));
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    return List<String>.from(payload['models'] as List<dynamic>? ?? []);
  }

  Future<Map<String, dynamic>> platformLogin(
    String platform,
    String username,
    String password,
  ) async {
    final response = await http.post(
      Uri.parse('$_baseUrl/api/platforms/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'platform': platform,
        'username': username,
        'password': password,
      }),
    );
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> platformStatus() async {
    final response = await http.get(Uri.parse('$_baseUrl/api/platforms/status'));
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    return List<Map<String, dynamic>>.from(
      payload['platforms'] as List<dynamic>? ?? [],
    );
  }

  Future<Map<String, dynamic>> loadCredentials() async {
    final response = await http.get(Uri.parse('$_baseUrl/api/credentials'));
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<void> saveCredentials(Map<String, dynamic> credentials) async {
    await http.post(
      Uri.parse('$_baseUrl/api/credentials'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'credentials': credentials}),
    );
  }

  Future<Map<String, dynamic>> startRun(Map<String, dynamic> payload) async {
    final response = await http.post(
      Uri.parse('$_baseUrl/api/runs'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getRun(String runId) async {
    final response = await http.get(Uri.parse('$_baseUrl/api/runs/$runId'));
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  /// Fetch ALL raw collected documents as JSON (full dataset from disk).
  Future<Map<String, dynamic>> exportRaw(String runId) async {
    final response = await http.get(
      Uri.parse('$_baseUrl/api/runs/$runId/export/raw'),
    );
    if (response.statusCode != 200) {
      throw Exception('Raw JSON export failed: ${response.statusCode}');
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  /// Fetch ALL cleaned documents as JSON (full dataset from disk).
  Future<Map<String, dynamic>> exportClean(String runId) async {
    final response = await http.get(
      Uri.parse('$_baseUrl/api/runs/$runId/export/clean'),
    );
    if (response.statusCode != 200) {
      throw Exception('Clean JSON export failed: ${response.statusCode}');
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  /// Download raw documents as CSV bytes.
  Future<List<int>> exportRawCsv(String runId) async {
    return _downloadBytes('/api/runs/$runId/export/raw/csv', 'Raw CSV');
  }

  /// Download clean documents as CSV bytes (server-generated during run).
  Future<List<int>> exportCleanCsv(String runId) async {
    return _downloadBytes('/api/runs/$runId/export/clean/csv', 'Clean CSV');
  }

  /// Download clean documents as Markdown bytes (server-generated during run).
  Future<List<int>> exportCleanMarkdown(String runId) async {
    return _downloadBytes('/api/runs/$runId/export/clean/markdown', 'Clean Markdown');
  }

  /// Download a ZIP bundle of all export formats for a run.
  Future<List<int>> exportZip(String runId) async {
    return _downloadBytes('/api/runs/$runId/export/zip', 'ZIP bundle');
  }

  // ── Intelligence endpoints ─────────────────────────────────────────────

  Future<Map<String, dynamic>> getKnowledgeGraph(String runId) async {
    final response = await http.get(Uri.parse('$_baseUrl/api/runs/$runId/knowledge-graph'));
    if (response.statusCode != 200) return {};
    return Map<String, dynamic>.from(jsonDecode(response.body) as Map);
  }

  Future<Map<String, dynamic>> getGapAnalysis(String runId) async {
    final response = await http.get(Uri.parse('$_baseUrl/api/runs/$runId/gap-analysis'));
    if (response.statusCode != 200) return {};
    return Map<String, dynamic>.from(jsonDecode(response.body) as Map);
  }

  Future<List<Map<String, dynamic>>> getImages(String runId) async {
    final response = await http.get(Uri.parse('$_baseUrl/api/runs/$runId/images'));
    if (response.statusCode != 200) return [];
    final data = jsonDecode(response.body) as Map;
    return List<Map<String, dynamic>>.from(data['images'] as List? ?? []);
  }

  /// Generic bytes downloader used by all non-JSON export methods.
  Future<List<int>> _downloadBytes(String path, String label) async {
    final response = await http.get(Uri.parse('$_baseUrl$path'));
    if (response.statusCode != 200) {
      throw Exception('$label download failed: ${response.statusCode}');
    }
    return response.bodyBytes;
  }

  // ── ARIA 5.0: Domains & Countries ────────────────────────────────────────

  Future<Map<String, dynamic>> getDomains() async {
    try {
      final response = await http.get(Uri.parse('$_baseUrl/api/domains'));
      if (response.statusCode != 200) return {};
      return jsonDecode(response.body) as Map<String, dynamic>;
    } catch (_) { return {}; }
  }

  Future<Map<String, dynamic>> getCountries() async {
    try {
      final response = await http.get(Uri.parse('$_baseUrl/api/domains/countries'));
      if (response.statusCode != 200) return {};
      return jsonDecode(response.body) as Map<String, dynamic>;
    } catch (_) { return {}; }
  }

  Future<Map<String, dynamic>> analyzeDomains(String topic, String intent) async {
    try {
      final response = await http.post(
        Uri.parse('$_baseUrl/api/domains/analyze'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'topic': topic, 'intent': intent}),
      );
      if (response.statusCode != 200) return {};
      return jsonDecode(response.body) as Map<String, dynamic>;
    } catch (_) { return {}; }
  }

  Future<Map<String, dynamic>> analyzeIntent(String topic, String intent) async {
    try {
      final response = await http.post(
        Uri.parse('$_baseUrl/api/chat/analyze'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'topic': topic, 'intent': intent}),
      );
      if (response.statusCode != 200) return {};
      return jsonDecode(response.body) as Map<String, dynamic>;
    } catch (_) { return {}; }
  }

  Future<List<Map<String, dynamic>>> listRuns() async {
    try {
      final response = await http.get(Uri.parse('$_baseUrl/api/runs'));
      if (response.statusCode != 200) return [];
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return List<Map<String, dynamic>>.from(data['runs'] as List? ?? []);
    } catch (_) { return []; }
  }
}
