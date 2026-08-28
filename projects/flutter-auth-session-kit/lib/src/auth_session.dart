import 'dart:convert';

/// Immutable credentials returned by an application's authentication backend.
final class AuthSession {
  const AuthSession({
    required this.accessToken,
    required this.refreshToken,
    required this.expiresAt,
    required this.userId,
  });

  final String accessToken;
  final String refreshToken;
  final DateTime expiresAt;
  final String userId;

  bool expiresWithin(DateTime now, Duration skew) =>
      !expiresAt.isAfter(now.toUtc().add(skew));

  Map<String, Object?> toJson() => <String, Object?>{
        'access_token': accessToken,
        'refresh_token': refreshToken,
        'expires_at': expiresAt.toUtc().toIso8601String(),
        'user_id': userId,
      };

  String encode() => jsonEncode(toJson());

  static AuthSession decode(String encoded) {
    final Object? decoded = jsonDecode(encoded);
    if (decoded is! Map<String, Object?>) {
      throw const FormatException('Session must be a JSON object.');
    }
    final accessToken = decoded['access_token'];
    final refreshToken = decoded['refresh_token'];
    final expiresAt = decoded['expires_at'];
    final userId = decoded['user_id'];
    if (accessToken is! String ||
        accessToken.isEmpty ||
        refreshToken is! String ||
        refreshToken.isEmpty ||
        expiresAt is! String ||
        userId is! String ||
        userId.isEmpty) {
      throw const FormatException('Session fields are missing or invalid.');
    }
    final parsedExpiry = DateTime.tryParse(expiresAt);
    if (parsedExpiry == null) {
      throw const FormatException('Session expiry is invalid.');
    }
    return AuthSession(
      accessToken: accessToken,
      refreshToken: refreshToken,
      expiresAt: parsedExpiry.toUtc(),
      userId: userId,
    );
  }
}
