# App Integration Guide

## Android SDK

### Installation (build.gradle)
```gradle
dependencies {
    implementation 'io.publishertools:android-sdk:1.0.0'
}
```

### Initialization (Application class)
```java
public class MyApp extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        PublisherTools.initialize(this, "PUB000001");
        // Test mode (remove in production)
        // PublisherTools.setTestMode(true);
    }
}
```

### Banner Ad
```java
AdView adView = new AdView(this);
adView.setAdUnitId("UNIT000001");
adView.setAdSize(AdSize.BANNER);
adView.loadAd(new AdRequest.Builder().build());
parentView.addView(adView);
```

### Interstitial Ad
```java
InterstitialAd interstitial = new InterstitialAd(this, "UNIT000002");
interstitial.setInterstitialAdLoadListener(new InterstitialAdLoadListener() {
    @Override
    public void onAdLoaded() {
        interstitial.show();
    }
});
interstitial.loadAd();
```

### Rewarded Video Ad
```java
RewardedAd rewardedAd = new RewardedAd(this, "UNIT000003");
rewardedAd.setRewardedAdListener(new RewardedAdListener() {
    @Override
    public void onUserEarnedReward(RewardItem reward) {
        // Grant reward: reward.getAmount() + " " + reward.getType()
    }
});
rewardedAd.loadAd();
```

---

## iOS SDK (Swift)

### Installation (Podfile)
```ruby
pod 'PublisherToolsSDK', '~> 1.0'
```

### Initialization (AppDelegate.swift)
```swift
import PublisherToolsSDK

func application(_ application: UIApplication, didFinishLaunchingWithOptions...) -> Bool {
    PublisherTools.initialize(publisherId: "PUB000001")
    return true
}
```

### Banner Ad
```swift
let adView = PTBannerAdView(frame: CGRect(x: 0, y: 0, width: 320, height: 50))
adView.unitId = "UNIT000001"
adView.rootViewController = self
adView.loadAd()
view.addSubview(adView)
```

---

## Flutter SDK

```dart
// pubspec.yaml
publisher_tools_sdk: ^1.0.0

// Initialize
await PublisherTools.initialize(publisherId: 'PUB000001');

// Banner
PublisherToolsBannerAd(unitId: 'UNIT000001', size: BannerAdSize.banner)
```

---

## Required Permissions

### Android (AndroidManifest.xml)
```xml
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
```

### iOS (Info.plist)
```xml
<key>NSUserTrackingUsageDescription</key>
<string>This app uses tracking to show you relevant ads</string>
```

## GDPR / COPPA Compliance
```java
// Request consent before showing ads
PublisherTools.requestConsent(this, consentType -> {
    if (consentType == ConsentType.PERSONALIZED) {
        adView.loadAd();
    }
});

// COPPA - if user is under 13
PublisherTools.setChildDirectedTreatment(true);
```
