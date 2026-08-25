# Resilient Feature Kit for Flutter

A small, dependency-free Flutter package for API-backed screens that must stay
useful through slow networks, refresh failures, repeated requests, and widget
disposal. It packages the state-management mechanics teams repeatedly rebuild
around repositories while remaining compatible with Provider, Riverpod, BLoC,
or direct `ChangeNotifier` usage.

The project targets Flutter 3.24+ and Dart 3.5+. Remote CI uses Flutter's stable
channel; Flutter 3.47 became stable on August 12, 2026.

## What is included

- Exhaustive idle, loading, success, stale, and failure state types
- Previous-data retention during refresh and refresh failure
- Stale-while-revalidate memory caching with a configurable TTL
- Bounded exponential retries with an injectable retry predicate and sleeper
- In-flight request coalescing by key
- Optimistic updates with confirmed commit or rollback
- Generation tokens that ignore late results after refresh or disposal
- Reusable Material `LoadStateView` for loading, empty, stale, data, and error UI
- Accessible live-region status messaging
- A runnable interactive example with refresh and simulated-failure controls
- Unit and widget tests with no third-party runtime dependencies

## Architecture

```text
Feature repository / API client
            |
       QueryController<T>
       /      |       \
  Cache   RetryPolicy  RequestCoalescer
       \      |       /
          LoadState<T>
               |
        LoadStateView<T>
```

The controller accepts a fetch function rather than owning HTTP code. Network,
database, and serialization choices therefore remain in the consuming app's
data layer.

## Use it

Copy the package into a workspace or reference its path from another Flutter
project:

```yaml
dependencies:
  resilient_feature_kit:
    path: ../flutter-resilient-feature-kit
```

Create a controller near the feature's view model or state owner:

```dart
final controller = QueryController<List<Order>>(
  fetcher: orderRepository.fetchOrders,
  cacheKey: 'orders:${user.id}',
  cacheStore: MemoryCacheStore(),
  cacheTimeToLive: const Duration(minutes: 5),
  retryPolicy: RetryPolicy(
    maxAttempts: 3,
    shouldRetry: (error) => error is TimeoutException,
  ),
);

await controller.load();
```

Render every state explicitly:

```dart
LoadStateView<List<Order>>(
  state: controller.state,
  onRetry: controller.refresh,
  isEmpty: (orders) => orders.isEmpty,
  dataBuilder: (context, orders) => OrdersList(orders: orders),
)
```

Apply an optimistic update without losing rollback data:

```dart
final committed = await controller.replaceOptimistically(
  editedOrders,
  () => orderRepository.save(editedOrders),
);
```

## Run the example

```bash
flutter pub get
cd example
flutter pub get
flutter run -d chrome
```

The example intentionally uses a fake repository. It demonstrates state and
failure behaviour without claiming a live backend integration. The values in
`.env.example` are safe configuration examples for a consuming application;
this package does not load dotenv files.

## Validate

```bash
flutter analyze
flutter test
```

Tests cover cache type safety and expiry, backoff boundaries, coalescing,
fresh-cache short-circuiting, stale refresh, retry success, retained failure
data, optimistic commit and rollback, disposal safety, and all UI states.

## Production integration notes

- Inject a disk-backed `CacheStore` if data must survive process termination.
- Keep authentication and HTTP clients in the repository layer.
- Use stable cache keys that include the current tenant or user where needed.
- Restrict retries to transient failures such as timeouts and 5xx responses.
- Dispose controllers from the owning widget, Provider, or dependency scope.
- Do not cache regulated or sensitive data without encryption and a retention
  policy.

## Honest limitations

- `MemoryCacheStore` is process-local and deliberately has no disk persistence.
- Request coalescing is in-process, not distributed across devices or isolates.
- Retry delays are deterministic. Add bounded jitter at the application edge
  if many clients could retry the same outage simultaneously.
- The example has web scaffolding only. Generate Android and iOS host folders
  in the example if physical-device demonstration is required.
- Flutter was unavailable in the local authoring environment. Compilation,
  analysis, and Flutter tests are delegated to the checked-in GitHub Actions
  job and must pass before merge.

## References

- [Flutter testing overview](https://docs.flutter.dev/testing/overview)
- [Flutter architecture testing guidance](https://docs.flutter.dev/app-architecture/case-study/testing)
- [Flutter 3.47 release notes](https://docs.flutter.dev/release/release-notes/release-notes-3.47.0)
