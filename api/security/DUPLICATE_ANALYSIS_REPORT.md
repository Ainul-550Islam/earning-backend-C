# Security Module Duplicate Analysis Report

**Generated on:** 2026-04-25 13:53:37
**Total Files Analyzed:** 138

## 📊 Summary

- **Duplicate Classes:** 79
- **Duplicate Functions:** 384
- **Duplicate Imports:** 363

## 🏷️ Duplicate Classes (A-Z)

### AuditTrailFactory

1. **factories.py** (Line 395)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 364)
   - Inherits from: DjangoModelFactory

### AuditTrailViewSet

1. **views.py** (Line 10054)
   - Inherits from: ReadOnlyModelViewSet
2. **viewset.py** (Line 277)
   - Inherits from: BaseSecurityViewSet

### BaseSecurityPermission

1. **permissions.py** (Line 31)
   - Inherits from: BasePermission
2. **permissions_backup.py** (Line 31)
   - Inherits from: BasePermission

### BaseSecurityTest

1. **tests.py** (Line 54)
   - Inherits from: APITestCase
2. **tests.py** (Line 294)
   - Inherits from: TestCase

### BulkSecurityDataFactory

1. **factories.py** (Line 427)
2. **factories_backup.py** (Line 395)

### BulletproofDecorator

1. **decorators.py** (Line 619)
2. **utils\cache_manager.py** (Line 492)

### CanManageDevices

1. **permissions.py** (Line 206)
   - Inherits from: BaseSecurityPermission
2. **views.py** (Line 198)
   - Inherits from: BasePermission
3. **views.py** (Line 244)
   - Inherits from: BasePermission
4. **views.py** (Line 516)
   - Inherits from: BasePermission

### CircuitBreakerOpenException

1. **integration_system\circuit_breaker.py** (Line 164)
   - Inherits from: Exception
2. **integration_system\integ_exceptions.py** (Line 163)
   - Inherits from: IntegrationException

### CombinedPermission

1. **permissions.py** (Line 321)
   - Inherits from: BaseSecurityPermission
2. **permissions_backup.py** (Line 530)
   - Inherits from: BaseSecurityPermission

### Command

1. **management\commands\block_suspicious_ips.py** (Line 29)
   - Inherits from: BaseCommand
2. **management\commands\export_security_report.py** (Line 32)
   - Inherits from: BaseCommand
3. **management\commands\run_security_scan.py** (Line 31)
   - Inherits from: BaseCommand
4. **management\commands\seed_security_rules.py** (Line 28)
   - Inherits from: BaseCommand
5. **management\commands\unlock_user_accounts.py** (Line 28)
   - Inherits from: BaseCommand

### DataValidator

1. **admin.py** (Line 6773)
2. **integration_system\data_validator.py** (Line 234)

### DeviceInfoFactory

1. **factories.py** (Line 67)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 47)
   - Inherits from: DjangoModelFactory
3. **tests\factories.py** (Line 50)
   - Inherits from: DjangoModelFactory

### DeviceInfoFilter

1. **filters.py** (Line 400)
   - Inherits from: FilterSet
2. **views.py** (Line 407)
   - Inherits from: FilterSet

### DeviceInfoManager

1. **managers.py** (Line 375)
   - Inherits from: Manager
2. **models.py** (Line 609)
   - Inherits from: Manager

### DeviceInfoModelTest

1. **test_models.py** (Line 24)
   - Inherits from: TestCase
2. **tests\test_security_models.py** (Line 34)
   - Inherits from: TestCase

### DeviceInfoViewSetTest

1. **test_views.py** (Line 64)
   - Inherits from: BaseSecurityViewTest
2. **tests\test_security_views.py** (Line 35)
   - Inherits from: APITestCase

### GracefulDegradation

1. **models.py** (Line 102)
2. **models.py** (Line 3466)
3. **utils\__init__.py** (Line 27)

### HasSecurityPermission

1. **permissions.py** (Line 242)
   - Inherits from: BaseSecurityPermission
2. **permissions_backup.py** (Line 207)
   - Inherits from: BaseSecurityPermission

### IPBlacklistFactory

1. **factories.py** (Line 139)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 118)
   - Inherits from: DjangoModelFactory
3. **tests\factories.py** (Line 130)
   - Inherits from: DjangoModelFactory

### IPWhitelistPermission

1. **permissions.py** (Line 287)
   - Inherits from: BaseSecurityPermission
2. **permissions_backup.py** (Line 450)
   - Inherits from: BaseSecurityPermission

### IsAdminOrSecurityTeam

1. **permissions.py** (Line 79)
   - Inherits from: BaseSecurityPermission
2. **permissions_backup.py** (Line 78)
   - Inherits from: BaseSecurityPermission
3. **views.py** (Line 4051)
   - Inherits from: BasePermission
4. **views.py** (Line 5051)
   - Inherits from: BasePermission
5. **views.py** (Line 5785)
   - Inherits from: BasePermission
6. **views.py** (Line 6840)
   - Inherits from: BasePermission

### IsSecurityAdmin

1. **mixins.py** (Line 499)
   - Inherits from: BasePermission
2. **permissions.py** (Line 124)
   - Inherits from: BaseSecurityPermission
3. **permissions_backup.py** (Line 122)
   - Inherits from: BaseSecurityPermission
4. **views.py** (Line 167)
   - Inherits from: BasePermission
5. **views.py** (Line 268)
   - Inherits from: BasePermission
6. **views.py** (Line 537)
   - Inherits from: BasePermission

### IsStaffUser

1. **permissions.py** (Line 48)
   - Inherits from: BaseSecurityPermission
2. **permissions_backup.py** (Line 48)
   - Inherits from: BaseSecurityPermission

### IsSuperUser

1. **permissions.py** (Line 63)
   - Inherits from: BaseSecurityPermission
2. **permissions_backup.py** (Line 63)
   - Inherits from: BaseSecurityPermission
3. **permissions_backup.py** (Line 693)
   - Inherits from: BasePermission

### Meta

1. **abstracts.py** (Line 28)
2. **abstracts.py** (Line 65)
3. **abstracts.py** (Line 77)
4. **factories.py** (Line 48)
5. **factories.py** (Line 70)
6. **factories.py** (Line 101)
7. **factories.py** (Line 128)
8. **factories.py** (Line 142)
9. **factories.py** (Line 156)
10. **factories.py** (Line 178)
11. **factories.py** (Line 211)
12. **factories.py** (Line 231)
13. **factories.py** (Line 249)
14. **factories.py** (Line 278)
15. **factories.py** (Line 307)
16. **factories.py** (Line 331)
17. **factories.py** (Line 354)
18. **factories.py** (Line 373)
19. **factories.py** (Line 398)
20. **factories_backup.py** (Line 28)
21. **factories_backup.py** (Line 50)
22. **factories_backup.py** (Line 81)
23. **factories_backup.py** (Line 108)
24. **factories_backup.py** (Line 121)
25. **factories_backup.py** (Line 134)
26. **factories_backup.py** (Line 160)
27. **factories_backup.py** (Line 189)
28. **factories_backup.py** (Line 214)
29. **factories_backup.py** (Line 233)
30. **factories_backup.py** (Line 259)
31. **factories_backup.py** (Line 292)
32. **factories_backup.py** (Line 309)
33. **factories_backup.py** (Line 325)
34. **factories_backup.py** (Line 343)
35. **factories_backup.py** (Line 367)
36. **feature_flags.py** (Line 88)
37. **filters.py** (Line 60)
38. **filters.py** (Line 165)
39. **filters.py** (Line 210)
40. **filters.py** (Line 294)
41. **filters.py** (Line 350)
42. **filters.py** (Line 391)
43. **filters.py** (Line 430)
44. **filters.py** (Line 475)
45. **filters.py** (Line 514)
46. **filters.py** (Line 561)
47. **filters.py** (Line 596)
48. **filters.py** (Line 622)
49. **filters.py** (Line 659)
50. **forms.py** (Line 22)
51. **forms.py** (Line 70)
52. **forms.py** (Line 116)
53. **forms.py** (Line 143)
54. **hash_chain.py** (Line 64)
55. **models.py** (Line 208)
56. **models.py** (Line 752)
57. **models.py** (Line 946)
58. **models.py** (Line 1041)
59. **models.py** (Line 1160)
60. **models.py** (Line 1311)
61. **models.py** (Line 1399)
62. **models.py** (Line 1494)
63. **models.py** (Line 1595)
64. **models.py** (Line 1691)
65. **models.py** (Line 1775)
66. **models.py** (Line 1876)
67. **models.py** (Line 1957)
68. **models.py** (Line 2021)
69. **models.py** (Line 2167)
70. **models.py** (Line 2266)
71. **models.py** (Line 2400)
72. **models.py** (Line 2454)
73. **models.py** (Line 2587)
74. **models.py** (Line 2625)
75. **models.py** (Line 2712)
76. **models.py** (Line 2816)
77. **models.py** (Line 2861)
78. **models.py** (Line 2948)
79. **models.py** (Line 2980)
80. **models.py** (Line 3191)
81. **models.py** (Line 3429)
82. **models.py** (Line 3589)
83. **models.py** (Line 4239)
84. **models.py** (Line 4996)
85. **models.py** (Line 5527)
86. **models.py** (Line 6133)
87. **models.py** (Line 6595)
88. **models.py** (Line 7474)
89. **models.py** (Line 8180)
90. **models.py** (Line 8272)
91. **models.py** (Line 8368)
92. **models.py** (Line 8423)
93. **models.py** (Line 8484)
94. **models.py** (Line 8582)
95. **model_mixins.py** (Line 19)
96. **model_mixins.py** (Line 42)
97. **model_mixins.py** (Line 61)
98. **model_mixins.py** (Line 87)
99. **model_mixins.py** (Line 120)
100. **model_mixins.py** (Line 156)
101. **model_mixins.py** (Line 195)
102. **model_mixins.py** (Line 232)
103. **model_mixins.py** (Line 271)
104. **model_mixins.py** (Line 302)
105. **model_mixins.py** (Line 329)
106. **model_mixins.py** (Line 366)
107. **notifications_push.py** (Line 108)
108. **notifications_push.py** (Line 175)
109. **sanctions.py** (Line 116)
110. **sanctions.py** (Line 266)
111. **serializers.py** (Line 3274)
112. **serializers.py** (Line 3466)
113. **serializers.py** (Line 3496)
114. **serializers.py** (Line 3541)
   - Inherits from: Meta
115. **serializers.py** (Line 3945)
116. **serializers.py** (Line 4675)
117. **serializers.py** (Line 4756)
118. **serializers.py** (Line 4856)
119. **serializers.py** (Line 5093)
120. **serializers.py** (Line 5160)
121. **serializers.py** (Line 5414)
122. **serializers.py** (Line 5646)
123. **serializers.py** (Line 5702)
124. **serializers.py** (Line 6059)
125. **serializers.py** (Line 6360)
126. **serializers.py** (Line 6791)
127. **serializers.py** (Line 7090)
128. **serializers.py** (Line 7145)
129. **serializers.py** (Line 7397)
130. **serializers.py** (Line 7578)
131. **serializers.py** (Line 7613)
132. **serializers.py** (Line 7656)
133. **serializers.py** (Line 7804)
134. **serializers.py** (Line 8166)
135. **serializers.py** (Line 8728)
136. **serializers.py** (Line 8862)
137. **serializers.py** (Line 8968)
138. **serializers.py** (Line 9557)
139. **serializers.py** (Line 9655)
140. **serializers.py** (Line 10285)
141. **serializers.py** (Line 10411)
142. **serializers.py** (Line 10475)
143. **serializers.py** (Line 10530)
144. **serializers.py** (Line 10585)
145. **serializers.py** (Line 10643)
146. **serializers.py** (Line 10688)
147. **serializers.py** (Line 10745)
148. **serializers.py** (Line 10806)
149. **serializers.py** (Line 11035)
150. **serializers.py** (Line 11665)
151. **serializers.py** (Line 11791)
152. **serializers.py** (Line 11814)
153. **serializers.py** (Line 11883)
154. **serializers.py** (Line 11916)
155. **serializers.py** (Line 11955)
156. **serializers.py** (Line 12028)
157. **serializers.py** (Line 12068)
158. **serializers.py** (Line 12104)
159. **serializers.py** (Line 12149)
160. **serializers.py** (Line 12185)
161. **serializers.py** (Line 12205)
162. **serializers.py** (Line 12220)
163. **serializers.py** (Line 12234)
164. **serializers.py** (Line 12247)
165. **views.py** (Line 214)
166. **views.py** (Line 408)
167. **views.py** (Line 10045)
168. **webhooks.py** (Line 103)
169. **webhooks.py** (Line 202)
170. **tests\factories.py** (Line 24)
171. **tests\factories.py** (Line 53)
172. **tests\factories.py** (Line 80)
173. **tests\factories.py** (Line 92)
174. **tests\factories.py** (Line 116)
175. **tests\factories.py** (Line 133)
176. **tests\factories.py** (Line 150)
177. **tests\factories.py** (Line 170)
178. **tests\factories.py** (Line 195)
179. **tests\factories.py** (Line 211)
180. **tests\factories.py** (Line 226)
181. **tests\factories.py** (Line 256)
182. **tests\factories.py** (Line 276)
183. **tests\factories.py** (Line 298)
184. **tests\factories.py** (Line 317)
185. **tests\factories.py** (Line 337)
186. **tests\factories.py** (Line 355)
187. **tests\factories.py** (Line 372)
188. **tests\factories.py** (Line 387)
189. **tests\factories.py** (Line 402)
190. **tests\factories.py** (Line 418)
191. **tests\factories.py** (Line 435)
192. **tests\factories.py** (Line 451)
193. **tests\factories.py** (Line 472)

### Migration

1. **migrations\0001_initial.py** (Line 10)
   - Inherits from: Migration
2. **migrations\0002_initial.py** (Line 8)
   - Inherits from: Migration
3. **migrations\0003_rename_security_ap_version_305516_idx_idx_version_code_is_active_1718_and_more.py** (Line 6)
   - Inherits from: Migration
4. **migrations\0004_rename_idx_version_code_is_active_1718_idx_version_code_is_active_394_and_more.py** (Line 6)
   - Inherits from: Migration
5. **migrations\0005_add_threat_intelligence_and_security_incident.py** (Line 12)
   - Inherits from: Migration
6. **migrations\0006_update_system_integrations.py** (Line 11)
   - Inherits from: Migration
7. **migrations\0007_add_missing_security_models.py** (Line 11)
   - Inherits from: Migration

### NullSafe

1. **models.py** (Line 76)
2. **utils\__init__.py** (Line 12)

### NullSafeSerializerMixin

1. **serializers.py** (Line 3599)
2. **serializers.py** (Line 3692)

### PasswordHistory

1. **models.py** (Line 2565)
   - Inherits from: Model
2. **models.py** (Line 8394)
   - Inherits from: Model

### PasswordHistoryAdmin

1. **admin.py** (Line 3975)
   - Inherits from: ModelAdmin
2. **admin.py** (Line 4618)
   - Inherits from: ModelAdmin

### PasswordHistoryFactory

1. **factories.py** (Line 228)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 211)
   - Inherits from: DjangoModelFactory
3. **tests\factories.py** (Line 192)
   - Inherits from: DjangoModelFactory

### PasswordPolicy

1. **constants.py** (Line 42)
2. **models.py** (Line 2415)
   - Inherits from: Model

### RateLimitExceeded

1. **decorators.py** (Line 325)
   - Inherits from: SecurityException
2. **serializers.py** (Line 77)
   - Inherits from: SecurityException

### RealTimeDetectionControlSerializer

1. **serializers.py** (Line 10294)
   - Inherits from: Serializer
2. **serializers.py** (Line 11674)
   - Inherits from: Serializer

### RealTimeDetectionResultSerializer

1. **serializers.py** (Line 10360)
   - Inherits from: Serializer
2. **serializers.py** (Line 11740)
   - Inherits from: Serializer

### RealTimeDetectionSerializer

1. **serializers.py** (Line 9566)
   - Inherits from: ModelSerializer
2. **serializers.py** (Line 10946)
   - Inherits from: ModelSerializer

### RealTimeDetectionStatusSerializer

1. **serializers.py** (Line 10248)
   - Inherits from: Serializer
2. **serializers.py** (Line 11628)
   - Inherits from: Serializer

### RiskScoreFactory

1. **factories.py** (Line 304)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 289)
   - Inherits from: DjangoModelFactory
3. **tests\factories.py** (Line 253)
   - Inherits from: DjangoModelFactory

### RiskScoreModelTest

1. **test_models.py** (Line 564)
   - Inherits from: TestCase
2. **tests\test_security_models.py** (Line 518)
   - Inherits from: TestCase

### SecurityAdminSite

1. **admin.py** (Line 4941)
   - Inherits from: AdminSite
2. **admin.py** (Line 7094)
   - Inherits from: AdminSite
3. **admin.py** (Line 7666)
   - Inherits from: AdminSite

### SecurityCache

1. **abstracts.py** (Line 561)
   - Inherits from: ABC
2. **caching.py** (Line 53)

### SecurityConfig

1. **apps.py** (Line 14)
   - Inherits from: AppConfig
2. **models.py** (Line 5410)
   - Inherits from: Model

### SecurityDashboardView

1. **serializers.py** (Line 1072)
   - Inherits from: BaseAPIView
2. **views.py** (Line 9653)
   - Inherits from: APIView

### SecurityException

1. **common_imports.py** (Line 283)
   - Inherits from: Exception
2. **decorators.py** (Line 321)
   - Inherits from: Exception
3. **exceptions.py** (Line 17)
   - Inherits from: Exception
4. **serializers.py** (Line 73)
   - Inherits from: Exception

### SecurityIncidentFactory

1. **factories.py** (Line 175)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 157)
   - Inherits from: DjangoModelFactory
3. **tests\factories.py** (Line 167)
   - Inherits from: DjangoModelFactory

### SecurityIncidentModelTest

1. **test_models.py** (Line 289)
   - Inherits from: TestCase
2. **tests\test_security_models.py** (Line 337)
   - Inherits from: TestCase

### SecurityIncidentViewSetTest

1. **test_views.py** (Line 456)
   - Inherits from: BaseSecurityViewTest
2. **tests\test_security_views.py** (Line 665)
   - Inherits from: APITestCase

### SecurityInsightFactory

1. **factories.py** (Line 275)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 256)
   - Inherits from: DjangoModelFactory
3. **tests\factories.py** (Line 223)
   - Inherits from: DjangoModelFactory

### SecurityInsightModelTest

1. **test_models.py** (Line 479)
   - Inherits from: TestCase
2. **tests\test_security_models.py** (Line 476)
   - Inherits from: TestCase

### SecurityInsightViewSetTest

1. **test_views.py** (Line 757)
   - Inherits from: BaseSecurityViewTest
2. **tests\test_security_views.py** (Line 1167)
   - Inherits from: APITestCase

### SecurityLogFactory

1. **factories.py** (Line 98)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 78)
   - Inherits from: DjangoModelFactory
3. **tests\factories.py** (Line 89)
   - Inherits from: DjangoModelFactory

### SecurityLogFilter

1. **filters.py** (Line 22)
   - Inherits from: FilterSet
2. **views.py** (Line 211)
   - Inherits from: FilterSet

### SecurityLogModelTest

1. **test_models.py** (Line 115)
   - Inherits from: TestCase
2. **tests\test_security_models.py** (Line 145)
   - Inherits from: TestCase

### SecurityLogViewSetTest

1. **test_views.py** (Line 241)
   - Inherits from: BaseSecurityViewTest
2. **tests\test_security_views.py** (Line 165)
   - Inherits from: APITestCase

### SecurityMonitor

1. **abstracts.py** (Line 213)
   - Inherits from: ABC
2. **monitoring.py** (Line 51)

### SecurityNotificationFactory

1. **factories.py** (Line 370)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 340)
   - Inherits from: DjangoModelFactory

### SecurityPolicy

1. **abstracts.py** (Line 493)
   - Inherits from: ABC
2. **models.py** (Line 8440)
   - Inherits from: Model

### SecurityPolicyFactory

1. **factories.py** (Line 246)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 230)
   - Inherits from: DjangoModelFactory
3. **tests\factories.py** (Line 208)
   - Inherits from: DjangoModelFactory

### SecurityPolicyModelTest

1. **test_models.py** (Line 433)
   - Inherits from: TestCase
2. **tests\test_security_models.py** (Line 438)
   - Inherits from: TestCase

### SecurityPolicyViewSetTest

1. **test_views.py** (Line 672)
   - Inherits from: BaseSecurityViewTest
2. **tests\test_security_views.py** (Line 1022)
   - Inherits from: APITestCase

### SecurityService

1. **abstracts.py** (Line 84)
   - Inherits from: ABC
2. **services.py** (Line 41)

### SecurityThrottle

1. **throttling.py** (Line 35)
   - Inherits from: BaseThrottle
2. **views.py** (Line 107)
   - Inherits from: UserRateThrottle

### SecurityViewsIntegrationTest

1. **test_views.py** (Line 852)
   - Inherits from: APITestCase
2. **tests\test_security_views.py** (Line 1293)
   - Inherits from: TransactionTestCase

### SuspiciousActivityDetected

1. **decorators.py** (Line 329)
   - Inherits from: SecurityException
2. **serializers.py** (Line 81)
   - Inherits from: SecurityException

### ThreatIntelligence

1. **constants.py** (Line 161)
2. **models.py** (Line 8133)
   - Inherits from: Model

### ThreatIntelligenceFactory

1. **factories.py** (Line 153)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 131)
   - Inherits from: DjangoModelFactory
3. **tests\factories.py** (Line 147)
   - Inherits from: DjangoModelFactory

### ThreatIntelligenceModelTest

1. **test_models.py** (Line 232)
   - Inherits from: TestCase
2. **tests\test_security_models.py** (Line 288)
   - Inherits from: TestCase

### ThreatIntelligenceViewSetTest

1. **test_views.py** (Line 349)
   - Inherits from: BaseSecurityViewTest
2. **tests\test_security_views.py** (Line 526)
   - Inherits from: APITestCase

### TimeRestrictedPermission

1. **permissions.py** (Line 262)
   - Inherits from: BaseSecurityPermission
2. **permissions_backup.py** (Line 496)
   - Inherits from: BaseSecurityPermission

### TrustedDeviceFactory

1. **factories.py** (Line 208)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 186)
   - Inherits from: DjangoModelFactory
3. **tests\factories.py** (Line 77)
   - Inherits from: DeviceInfoFactory

### TrustedDeviceModelTest

1. **test_models.py** (Line 367)
   - Inherits from: TestCase
2. **tests\test_security_models.py** (Line 104)
   - Inherits from: TestCase

### TrustedDeviceViewSetTest

1. **test_views.py** (Line 566)
   - Inherits from: BaseSecurityViewTest
2. **tests\test_security_views.py** (Line 808)
   - Inherits from: APITestCase

### TwoFactorMethodFactory

1. **factories.py** (Line 351)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 322)
   - Inherits from: DjangoModelFactory
3. **tests\factories.py** (Line 334)
   - Inherits from: DjangoModelFactory

### UserBanFactory

1. **factories.py** (Line 125)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 105)
   - Inherits from: DjangoModelFactory
3. **tests\factories.py** (Line 113)
   - Inherits from: DjangoModelFactory

### UserBanModelTest

1. **test_models.py** (Line 174)
   - Inherits from: TestCase
2. **tests\test_security_models.py** (Line 193)
   - Inherits from: TestCase

### UserFactory

1. **factories.py** (Line 45)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 25)
   - Inherits from: DjangoModelFactory
3. **tests\factories.py** (Line 21)
   - Inherits from: DjangoModelFactory

### UserSessionFactory

1. **factories.py** (Line 328)
   - Inherits from: BaseSecurityFactory
2. **factories_backup.py** (Line 306)
   - Inherits from: DjangoModelFactory
3. **tests\factories.py** (Line 295)
   - Inherits from: DjangoModelFactory

### UserSessionModelTest

1. **test_models.py** (Line 613)
   - Inherits from: TestCase
2. **tests\test_security_models.py** (Line 618)
   - Inherits from: TestCase

### ValidationFailed

1. **decorators.py** (Line 333)
   - Inherits from: SecurityException
2. **serializers.py** (Line 85)
   - Inherits from: SecurityException

## 🔧 Duplicate Functions (A-Z)

### __call__

1. **models.py** (Line 3473)
   - Arguments: (self, func)
2. **models.py** (Line 4650)
   - Arguments: (self, request)
3. **monitoring.py** (Line 680)
   - Arguments: (self, alert_data)
4. **monitoring.py** (Line 695)
   - Arguments: (self, alert_data)
5. **monitoring.py** (Line 727)
   - Arguments: (self, alert_data)
6. **monitoring.py** (Line 750)
   - Arguments: (self, alert_data)
7. **integration_system\circuit_breaker.py** (Line 347)
   - Arguments: (self, func)

### __init__

1. **abstracts.py** (Line 87)
   - Arguments: (self, name)
2. **abstracts.py** (Line 119)
   - Arguments: (self, validator_type)
3. **abstracts.py** (Line 141)
   - Arguments: (self, analyzer_type)
4. **abstracts.py** (Line 163)
   - Arguments: (self, detector_type)
5. **abstracts.py** (Line 194)
   - Arguments: (self, reporter_type)
6. **abstracts.py** (Line 216)
   - Arguments: (self, monitor_type)
7. **abstracts.py** (Line 244)
   - Arguments: (self, filter_type)
8. **abstracts.py** (Line 266)
   - Arguments: (self, processor_type)
9. **abstracts.py** (Line 288)
   - Arguments: (self, transformer_type)
10. **abstracts.py** (Line 310)
   - Arguments: (self, model_class)
11. **abstracts.py** (Line 351)
   - Arguments: (self, name)
12. **abstracts.py** (Line 386)
   - Arguments: (self, name)
13. **abstracts.py** (Line 412)
   - Arguments: (self, event_type)
14. **abstracts.py** (Line 443)
   - Arguments: (self, notifier_type)
15. **abstracts.py** (Line 474)
   - Arguments: (self, auditor_type)
16. **abstracts.py** (Line 496)
   - Arguments: (self, policy_name)
17. **abstracts.py** (Line 532)
   - Arguments: (self, enforcer_type)
18. **abstracts.py** (Line 564)
   - Arguments: (self, cache_type)
19. **abstracts.py** (Line 596)
   - Arguments: (self, logger_type)
20. **abstracts.py** (Line 618)
   - Arguments: (self, metrics_type)
21. **admin.py** (Line 6825)
   - Arguments: (self, queryset, model_name)
22. **admin.py** (Line 6900)
   - Arguments: (self)
23. **admin.py** (Line 7103)
   - Arguments: (self)
24. **admin.py** (Line 6649)
   - Arguments: (self)
25. **analytics.py** (Line 28)
   - Arguments: (self)
26. **caching.py** (Line 56)
   - Arguments: (self, cache_backend)
27. **caching.py** (Line 226)
   - Arguments: (self, cache)
28. **caching.py** (Line 285)
   - Arguments: (self, cache)
29. **caching.py** (Line 328)
   - Arguments: (self, cache)
30. **caching.py** (Line 366)
   - Arguments: (self, cache)
31. **caching.py** (Line 402)
   - Arguments: (self, cache)
32. **caching.py** (Line 430)
   - Arguments: (self, cache)
33. **caching.py** (Line 546)
   - Arguments: (self, cache)
34. **celery_beat_config.py** (Line 276)
   - Arguments: (self)
35. **compliance.py** (Line 45)
   - Arguments: (self, id, name, description, standard, category, mandatory)
36. **compliance.py** (Line 58)
   - Arguments: (self)
37. **compliance.py** (Line 201)
   - Arguments: (self, framework)
38. **compliance.py** (Line 778)
   - Arguments: (self)
39. **data_export.py** (Line 48)
   - Arguments: (self)
40. **dependencies.py** (Line 49)
   - Arguments: (self, config)
41. **dependencies.py** (Line 95)
   - Arguments: (self, config)
42. **dependencies.py** (Line 259)
   - Arguments: (self, config)
43. **dependencies.py** (Line 377)
   - Arguments: (self, config)
44. **dependencies.py** (Line 480)
   - Arguments: (self, config)
45. **dependencies.py** (Line 603)
   - Arguments: (self)
46. **duplicate_analyzer.py** (Line 15)
   - Arguments: (self, security_module_path)
47. **encryption.py** (Line 41)
   - Arguments: (self, key_id, algorithm, key_data, created_at, expires_at)
48. **encryption.py** (Line 80)
   - Arguments: (self)
49. **encryption.py** (Line 211)
   - Arguments: (self, key, algorithm)
50. **encryption.py** (Line 306)
   - Arguments: (self, private_key, public_key)
51. **encryption.py** (Line 421)
   - Arguments: (self)
52. **endpoint.py** (Line 82)
   - Arguments: (self, config)
53. **endpoint.py** (Line 151)
   - Arguments: (self)
54. **events.py** (Line 29)
   - Arguments: (self, event_type, data)
55. **events.py** (Line 59)
   - Arguments: (self, auth_type, success, user)
56. **events.py** (Line 90)
   - Arguments: (self, action, resource, user)
57. **events.py** (Line 143)
   - Arguments: (self, threat_type, indicator, severity)
58. **events.py** (Line 170)
   - Arguments: (self, incident_type, action, incident)
59. **events.py** (Line 199)
   - Arguments: (self, system_type, status)
60. **events.py** (Line 238)
   - Arguments: (self)
61. **events.py** (Line 621)
   - Arguments: (self, event_manager)
62. **exceptions.py** (Line 23)
   - Arguments: (self, message, error_code, context, severity, user_id, ip_address)
63. **exceptions.py** (Line 95)
   - Arguments: (self, message, lock_type, lock_duration, lock_reason, unlock_time)
64. **exceptions.py** (Line 153)
   - Arguments: (self, message, activity_type, threat_level, indicators, confidence)
65. **exceptions.py** (Line 212)
   - Arguments: (self, message, device_fingerprint, device_type, trust_level, risk_score)
66. **exceptions.py** (Line 267)
   - Arguments: (self, message, detection_type, confidence, vpn_provider)
67. **exceptions.py** (Line 294)
   - Arguments: (self, message, threat_type, threat_source, severity, indicators)
68. **exceptions.py** (Line 322)
   - Arguments: (self, message, limit_type, limit_count, reset_time)
69. **exceptions.py** (Line 355)
   - Arguments: (self, message, policy_violations, password_strength)
70. **exceptions.py** (Line 379)
   - Arguments: (self, message, config_key, config_value, expected_type)
71. **exceptions.py** (Line 406)
   - Arguments: (self, message, service_name, operation, service_error)
72. **feature_flags.py** (Line 255)
   - Arguments: (self)
73. **forms.py** (Line 32)
   - Arguments: (self)
74. **forms.py** (Line 89)
   - Arguments: (self)
75. **forms.py** (Line 127)
   - Arguments: (self)
76. **forms.py** (Line 154)
   - Arguments: (self)
77. **forms.py** (Line 222)
   - Arguments: (self, user)
78. **hash_chain.py** (Line 72)
   - Arguments: (self)
79. **hooks.py** (Line 27)
   - Arguments: (self, hook_name, description)
80. **hooks.py** (Line 100)
   - Arguments: (self)
81. **hooks.py** (Line 176)
   - Arguments: (self)
82. **hooks.py** (Line 264)
   - Arguments: (self)
83. **hooks.py** (Line 357)
   - Arguments: (self)
84. **hooks.py** (Line 456)
   - Arguments: (self)
85. **hooks.py** (Line 537)
   - Arguments: (self)
86. **interactors.py** (Line 32)
   - Arguments: (self)
87. **interactors.py** (Line 55)
   - Arguments: (self)
88. **interactors.py** (Line 196)
   - Arguments: (self)
89. **interactors.py** (Line 302)
   - Arguments: (self)
90. **interactors.py** (Line 500)
   - Arguments: (self)
91. **interactors.py** (Line 705)
   - Arguments: (self)
92. **logic.py** (Line 27)
   - Arguments: (self)
93. **logic.py** (Line 630)
   - Arguments: (self)
94. **mixins.py** (Line 142)
   - Arguments: (self)
95. **mixins.py** (Line 360)
   - Arguments: (self)
96. **models.py** (Line 3469)
   - Arguments: (self, default_return, log_error)
97. **models.py** (Line 4647)
   - Arguments: (self, get_response)
98. **monitoring.py** (Line 54)
   - Arguments: (self, name, monitor_type, interval)
99. **monitoring.py** (Line 167)
   - Arguments: (self, name, metric_name, threshold, comparison)
100. **monitoring.py** (Line 227)
   - Arguments: (self, name, event_type, threshold, time_window_minutes)
101. **monitoring.py** (Line 255)
   - Arguments: (self, threshold, time_window_minutes)
102. **monitoring.py** (Line 267)
   - Arguments: (self, threshold, time_window_minutes)
103. **monitoring.py** (Line 290)
   - Arguments: (self, threshold)
104. **monitoring.py** (Line 308)
   - Arguments: (self, threshold)
105. **monitoring.py** (Line 326)
   - Arguments: (self, name)
106. **monitoring.py** (Line 485)
   - Arguments: (self)
107. **monitoring.py** (Line 584)
   - Arguments: (self)
108. **monitoring.py** (Line 692)
   - Arguments: (self, recipients)
109. **monitoring.py** (Line 724)
   - Arguments: (self, webhook_url)
110. **notifications_push.py** (Line 193)
   - Arguments: (self)
111. **notifications_push.py** (Line 477)
   - Arguments: (self)
112. **notifications_push.py** (Line 525)
   - Arguments: (self)
113. **notifications_push.py** (Line 625)
   - Arguments: (self)
114. **notifications_push.py** (Line 665)
   - Arguments: (self, notification_service)
115. **openai.py** (Line 49)
   - Arguments: (self, config)
116. **pagination.py** (Line 159)
   - Arguments: (self, page_size, max_page_size, ordering)
117. **pagination.py** (Line 268)
   - Arguments: (self, page_size, max_page_size)
118. **pagination.py** (Line 302)
   - Arguments: (self, page_size, max_page_size)
119. **pagination.py** (Line 366)
   - Arguments: (self, page_size, max_page_size, aggregate_by)
120. **pagination.py** (Line 444)
   - Arguments: (self, default_type)
121. **pagination.py** (Line 510)
   - Arguments: (self, page_size, cache_timeout, cache_prefix)
122. **pagination.py** (Line 568)
   - Arguments: (self)
123. **permissions.py** (Line 247)
   - Arguments: (self, permission)
124. **permissions.py** (Line 267)
   - Arguments: (self, allowed_hours)
125. **permissions.py** (Line 292)
   - Arguments: (self, allowed_ips)
126. **permissions.py** (Line 326)
   - Arguments: (self)
127. **permissions_backup.py** (Line 212)
   - Arguments: (self, required_permissions)
128. **permissions_backup.py** (Line 315)
   - Arguments: (self, allowed_countries)
129. **permissions_backup.py** (Line 354)
   - Arguments: (self, max_risk_score)
130. **permissions_backup.py** (Line 429)
   - Arguments: (self, max_requests, time_window)
131. **permissions_backup.py** (Line 455)
   - Arguments: (self, whitelisted_ips)
132. **permissions_backup.py** (Line 501)
   - Arguments: (self, start_hour, end_hour)
133. **permissions_backup.py** (Line 535)
   - Arguments: (self)
134. **plugins.py** (Line 24)
   - Arguments: (self, name, version)
135. **plugins.py** (Line 154)
   - Arguments: (self)
136. **plugins.py** (Line 359)
   - Arguments: (self)
137. **plugins.py** (Line 400)
   - Arguments: (self)
138. **plugins.py** (Line 437)
   - Arguments: (self)
139. **plugins.py** (Line 483)
   - Arguments: (self)
140. **plugins.py** (Line 531)
   - Arguments: (self)
141. **plugins.py** (Line 577)
   - Arguments: (self)
142. **plugins.py** (Line 623)
   - Arguments: (self)
143. **plugins.py** (Line 658)
   - Arguments: (self)
144. **plugins.py** (Line 696)
   - Arguments: (self)
145. **plugins.py** (Line 740)
   - Arguments: (self)
146. **registry.py** (Line 73)
   - Arguments: (self)
147. **repositories.py** (Line 28)
   - Arguments: (self, model_class)
148. **repositories.py** (Line 130)
   - Arguments: (self)
149. **repositories.py** (Line 230)
   - Arguments: (self)
150. **repositories.py** (Line 315)
   - Arguments: (self)
151. **repositories.py** (Line 430)
   - Arguments: (self)
152. **repositories.py** (Line 514)
   - Arguments: (self)
153. **repositories.py** (Line 639)
   - Arguments: (self)
154. **resources.py** (Line 108)
   - Arguments: (self, config)
155. **resources.py** (Line 461)
   - Arguments: (self)
156. **resources.py** (Line 606)
   - Arguments: (self)
157. **sanctions.py** (Line 336)
   - Arguments: (self)
158. **sanctions.py** (Line 691)
   - Arguments: (self)
159. **schemas.py** (Line 21)
   - Arguments: (self, schema_type, version)
160. **schemas.py** (Line 38)
   - Arguments: (self)
161. **schemas.py** (Line 123)
   - Arguments: (self)
162. **schemas.py** (Line 225)
   - Arguments: (self)
163. **schemas.py** (Line 317)
   - Arguments: (self)
164. **schemas.py** (Line 428)
   - Arguments: (self)
165. **schemas.py** (Line 494)
   - Arguments: (self)
166. **schemas.py** (Line 581)
   - Arguments: (self)
167. **schemas.py** (Line 674)
   - Arguments: (self)
168. **search.py** (Line 27)
   - Arguments: (self, query_string, filters)
169. **search.py** (Line 135)
   - Arguments: (self, model_class, cache_timeout)
170. **search.py** (Line 361)
   - Arguments: (self, model_class, cache_timeout)
171. **search.py** (Line 522)
   - Arguments: (self)
172. **search.py** (Line 598)
   - Arguments: (self)
173. **selectors.py** (Line 22)
   - Arguments: (self, queryset)
174. **selectors.py** (Line 74)
   - Arguments: (self, queryset)
175. **selectors.py** (Line 202)
   - Arguments: (self, queryset)
176. **selectors.py** (Line 338)
   - Arguments: (self, queryset)
177. **selectors.py** (Line 482)
   - Arguments: (self, queryset)
178. **selectors.py** (Line 590)
   - Arguments: (self, queryset)
179. **serializers.py** (Line 3981)
   - Arguments: (self)
180. **serializers.py** (Line 7838)
   - Arguments: (self)
181. **serializers.py** (Line 8999)
   - Arguments: (self)
182. **serializers.py** (Line 9693)
   - Arguments: (self)
183. **serializers.py** (Line 11073)
   - Arguments: (self)
184. **services.py** (Line 48)
   - Arguments: (self)
185. **services.py** (Line 343)
   - Arguments: (self)
186. **services.py** (Line 476)
   - Arguments: (self)
187. **signals_cap.py** (Line 30)
   - Arguments: (self)
188. **signals_cap.py** (Line 265)
   - Arguments: (self, name)
189. **signals_cap.py** (Line 290)
   - Arguments: (self)
190. **signals_cap.py** (Line 363)
   - Arguments: (self)
191. **signals_cap.py** (Line 428)
   - Arguments: (self)
192. **signals_cap.py** (Line 518)
   - Arguments: (self, name)
193. **signals_cap.py** (Line 538)
   - Arguments: (self, min_severity)
194. **signals_cap.py** (Line 563)
   - Arguments: (self, allowed_users)
195. **signals_cap.py** (Line 599)
   - Arguments: (self, capture_instance)
196. **signals_kb.py** (Line 35)
   - Arguments: (self)
197. **signals_kb.py** (Line 199)
   - Arguments: (self, knowledge_manager)
198. **signals_kb.py** (Line 363)
   - Arguments: (self, knowledge_manager)
199. **signals_kb.py** (Line 449)
   - Arguments: (self, knowledge_manager)
200. **tasks.py** (Line 36)
   - Arguments: (self)
201. **tasks_cap.py** (Line 33)
   - Arguments: (self, name, description)
202. **tasks_cap.py** (Line 75)
   - Arguments: (self)
203. **tasks_cap.py** (Line 286)
   - Arguments: (self)
204. **tasks_cap.py** (Line 417)
   - Arguments: (self)
205. **tasks_cap.py** (Line 535)
   - Arguments: (self)
206. **tasks_cap.py** (Line 698)
   - Arguments: (self, capability_manager)
207. **tests.py** (Line 2348)
   - Arguments: (self)
208. **throttling.py** (Line 38)
   - Arguments: (self, rate, scope)
209. **throttling.py** (Line 190)
   - Arguments: (self, rate, burst_rate, scope)
210. **throttling.py** (Line 234)
   - Arguments: (self, base_rate, scope)
211. **throttling.py** (Line 296)
   - Arguments: (self, rates, default_rate, scope)
212. **throttling.py** (Line 330)
   - Arguments: (self, normal_rate, peak_rate, peak_hours, scope)
213. **throttling.py** (Line 355)
   - Arguments: (self, normal_rate, restricted_rate, restricted_countries, scope)
214. **throttling.py** (Line 387)
   - Arguments: (self, normal_rate, threat_rate, scope)
215. **throttling.py** (Line 425)
   - Arguments: (self, throttles, scope)
216. **throttling.py** (Line 454)
   - Arguments: (self)
217. **throttling.py** (Line 461)
   - Arguments: (self)
218. **throttling.py** (Line 468)
   - Arguments: (self)
219. **throttling.py** (Line 475)
   - Arguments: (self)
220. **throttling.py** (Line 488)
   - Arguments: (self)
221. **throttling.py** (Line 495)
   - Arguments: (self)
222. **throttling.py** (Line 502)
   - Arguments: (self)
223. **throttling.py** (Line 510)
   - Arguments: (self)
224. **use_cases.py** (Line 29)
   - Arguments: (self)
225. **use_cases.py** (Line 51)
   - Arguments: (self)
226. **use_cases.py** (Line 309)
   - Arguments: (self)
227. **use_cases.py** (Line 529)
   - Arguments: (self)
228. **use_cases.py** (Line 675)
   - Arguments: (self)
229. **views.py** (Line 599)
   - Arguments: (self)
230. **viewset.py** (Line 358)
   - Arguments: (self)
231. **viewset.py** (Line 436)
   - Arguments: (self)
232. **viewset_cap.py** (Line 26)
   - Arguments: (self, name, description, enabled)
233. **viewset_cap.py** (Line 39)
   - Arguments: (self, max_bulk_size, enabled)
234. **viewset_cap.py** (Line 140)
   - Arguments: (self, supported_formats, enabled)
235. **viewset_cap.py** (Line 266)
   - Arguments: (self, enabled)
236. **viewset_cap.py** (Line 385)
   - Arguments: (self, log_reads, log_writes, enabled)
237. **viewset_cap.py** (Line 547)
   - Arguments: (self, default_timeout, enabled)
238. **viewset_cap.py** (Line 648)
   - Arguments: (self)
239. **webhooks.py** (Line 31)
   - Arguments: (self, event_type, data, timestamp, metadata)
240. **webhooks.py** (Line 220)
   - Arguments: (self)
241. **webhooks.py** (Line 368)
   - Arguments: (self, webhook_manager)
242. **integration_system\auth_bridge.py** (Line 28)
   - Arguments: (self)
243. **integration_system\auth_bridge.py** (Line 144)
   - Arguments: (self)
244. **integration_system\auth_bridge.py** (Line 374)
   - Arguments: (self)
245. **integration_system\bridge.py** (Line 29)
   - Arguments: (self, name)
246. **integration_system\bridge.py** (Line 299)
   - Arguments: (self)
247. **integration_system\circuit_breaker.py** (Line 27)
   - Arguments: (self, name, failure_threshold, recovery_timeout, expected_exception, success_threshold)
248. **integration_system\circuit_breaker.py** (Line 172)
   - Arguments: (self)
249. **integration_system\circuit_breaker.py** (Line 343)
   - Arguments: (self, circuit_breaker_name, manager)
250. **integration_system\data_bridge.py** (Line 30)
   - Arguments: (self)
251. **integration_system\data_validator.py** (Line 28)
   - Arguments: (self, name, field, level)
252. **integration_system\data_validator.py** (Line 55)
   - Arguments: (self, field)
253. **integration_system\data_validator.py** (Line 66)
   - Arguments: (self, field, expected_type)
254. **integration_system\data_validator.py** (Line 78)
   - Arguments: (self, field, min_length, max_length)
255. **integration_system\data_validator.py** (Line 108)
   - Arguments: (self, field, pattern, flags)
256. **integration_system\data_validator.py** (Line 124)
   - Arguments: (self, field)
257. **integration_system\data_validator.py** (Line 133)
   - Arguments: (self, field)
258. **integration_system\data_validator.py** (Line 142)
   - Arguments: (self, field, min_value, max_value)
259. **integration_system\data_validator.py** (Line 175)
   - Arguments: (self, field, min_date, max_date)
260. **integration_system\data_validator.py** (Line 213)
   - Arguments: (self, field, choices)
261. **integration_system\data_validator.py** (Line 225)
   - Arguments: (self, field, validator_func, error_message)
262. **integration_system\data_validator.py** (Line 237)
   - Arguments: (self, name)
263. **integration_system\data_validator.py** (Line 416)
   - Arguments: (self)
264. **integration_system\event_bus.py** (Line 28)
   - Arguments: (self, event_type, data, source, target, priority, ttl)
265. **integration_system\event_bus.py** (Line 76)
   - Arguments: (self, name, event_types, handler, filter_func, async_handler)
266. **integration_system\event_bus.py** (Line 157)
   - Arguments: (self, name, max_queue_size)
267. **integration_system\event_bus.py** (Line 402)
   - Arguments: (self)
268. **integration_system\fallback_logic.py** (Line 27)
   - Arguments: (self, name, priority)
269. **integration_system\fallback_logic.py** (Line 109)
   - Arguments: (self, max_retries, base_delay, max_delay)
270. **integration_system\fallback_logic.py** (Line 166)
   - Arguments: (self, alternative_endpoints)
271. **integration_system\fallback_logic.py** (Line 236)
   - Arguments: (self, cache_ttl)
272. **integration_system\fallback_logic.py** (Line 294)
   - Arguments: (self, default_response)
273. **integration_system\fallback_logic.py** (Line 315)
   - Arguments: (self, degraded_functions)
274. **integration_system\fallback_logic.py** (Line 363)
   - Arguments: (self)
275. **integration_system\fallback_logic.py** (Line 492)
   - Arguments: (self)
276. **integration_system\health_check.py** (Line 27)
   - Arguments: (self, name, component_type)
277. **integration_system\health_check.py** (Line 151)
   - Arguments: (self, connection_name)
278. **integration_system\health_check.py** (Line 216)
   - Arguments: (self, api_name, endpoint_url, timeout)
279. **integration_system\health_check.py** (Line 296)
   - Arguments: (self, cache_name)
280. **integration_system\health_check.py** (Line 360)
   - Arguments: (self, queue_name)
281. **integration_system\health_check.py** (Line 430)
   - Arguments: (self, integration_name)
282. **integration_system\health_check.py** (Line 485)
   - Arguments: (self)
283. **integration_system\integ_adapter.py** (Line 26)
   - Arguments: (self, name, target_system)
284. **integration_system\integ_adapter.py** (Line 189)
   - Arguments: (self, name, base_url)
285. **integration_system\integ_adapter.py** (Line 295)
   - Arguments: (self, name, connection_string)
286. **integration_system\integ_adapter.py** (Line 405)
   - Arguments: (self, name, queue_url)
287. **integration_system\integ_adapter.py** (Line 496)
   - Arguments: (self)
288. **integration_system\integ_audit_logs.py** (Line 27)
   - Arguments: (self, name)
289. **integration_system\integ_audit_logs.py** (Line 369)
   - Arguments: (self)
290. **integration_system\integ_exceptions.py** (Line 17)
   - Arguments: (self, message, error_code, details)
291. **integration_system\integ_exceptions.py** (Line 38)
   - Arguments: (self, message, endpoint, status_code, response_text)
292. **integration_system\integ_exceptions.py** (Line 56)
   - Arguments: (self, message, auth_type, username)
293. **integration_system\integ_exceptions.py** (Line 70)
   - Arguments: (self, message, field, value, validation_rule)
294. **integration_system\integ_exceptions.py** (Line 88)
   - Arguments: (self, message, source_format, target_format, transformer_name)
295. **integration_system\integ_exceptions.py** (Line 106)
   - Arguments: (self, message, data_type, format_type)
296. **integration_system\integ_exceptions.py** (Line 120)
   - Arguments: (self, message, data_type, format_type)
297. **integration_system\integ_exceptions.py** (Line 134)
   - Arguments: (self, message, limit, window, retry_after)
298. **integration_system\integ_exceptions.py** (Line 152)
   - Arguments: (self, message, timeout_seconds, operation)
299. **integration_system\integ_exceptions.py** (Line 166)
   - Arguments: (self, message, circuit_name, failure_count)
300. **integration_system\integ_exceptions.py** (Line 180)
   - Arguments: (self, message, config_key, config_value)
301. **integration_system\integ_exceptions.py** (Line 194)
   - Arguments: (self, message, dependency_name, required_version)
302. **integration_system\integ_exceptions.py** (Line 208)
   - Arguments: (self, message, current_version, required_version)
303. **integration_system\integ_exceptions.py** (Line 223)
   - Arguments: (self, message, queue_name, queue_size)
304. **integration_system\integ_exceptions.py** (Line 237)
   - Arguments: (self, message, message_id, message_type)
305. **integration_system\integ_exceptions.py** (Line 251)
   - Arguments: (self, message, webhook_url, webhook_name)
306. **integration_system\integ_exceptions.py** (Line 265)
   - Arguments: (self, message, source_system, target_system, sync_rule)
307. **integration_system\integ_exceptions.py** (Line 283)
   - Arguments: (self, message, conflict_type, conflict_field, source_value, target_value)
308. **integration_system\integ_exceptions.py** (Line 304)
   - Arguments: (self, message, required_permission, user_id)
309. **integration_system\integ_exceptions.py** (Line 318)
   - Arguments: (self, message, resource_type, resource_id)
310. **integration_system\integ_exceptions.py** (Line 332)
   - Arguments: (self, message, attempt, max_attempts, next_retry)
311. **integration_system\integ_exceptions.py** (Line 350)
   - Arguments: (self, message, component_name, health_status)
312. **integration_system\integ_exceptions.py** (Line 364)
   - Arguments: (self, message, metric_name, metric_value)
313. **integration_system\integ_exceptions.py** (Line 378)
   - Arguments: (self, message, cache_key, cache_operation)
314. **integration_system\integ_exceptions.py** (Line 392)
   - Arguments: (self)
315. **integration_system\integ_handler.py** (Line 27)
   - Arguments: (self)
316. **integration_system\integ_handler.py** (Line 296)
   - Arguments: (self)
317. **integration_system\integ_registry.py** (Line 27)
   - Arguments: (self)
318. **integration_system\integ_signals.py** (Line 35)
   - Arguments: (self)
319. **integration_system\message_queue.py** (Line 30)
   - Arguments: (self, body, priority, ttl, delay, max_retries)
320. **integration_system\message_queue.py** (Line 97)
   - Arguments: (self, name, max_size, max_memory_mb)
321. **integration_system\message_queue.py** (Line 324)
   - Arguments: (self)
322. **integration_system\message_queue.py** (Line 450)
   - Arguments: (self)
323. **integration_system\performance_monitor.py** (Line 28)
   - Arguments: (self, name, unit, description)
324. **integration_system\performance_monitor.py** (Line 110)
   - Arguments: (self, name)
325. **integration_system\performance_monitor.py** (Line 306)
   - Arguments: (self)
326. **integration_system\performance_monitor.py** (Line 407)
   - Arguments: (self)
327. **integration_system\sync_manager.py** (Line 26)
   - Arguments: (self, name, priority)
328. **integration_system\sync_manager.py** (Line 53)
   - Arguments: (self)
329. **integration_system\sync_manager.py** (Line 71)
   - Arguments: (self)
330. **integration_system\sync_manager.py** (Line 89)
   - Arguments: (self)
331. **integration_system\sync_manager.py** (Line 157)
   - Arguments: (self)
332. **integration_system\sync_manager.py** (Line 216)
   - Arguments: (self)
333. **integration_system\sync_manager.py** (Line 252)
   - Arguments: (self)
334. **integration_system\transformer.py** (Line 28)
   - Arguments: (self, name, source_format, target_format)
335. **integration_system\transformer.py** (Line 136)
   - Arguments: (self, name)
336. **integration_system\transformer.py** (Line 161)
   - Arguments: (self, name)
337. **integration_system\transformer.py** (Line 245)
   - Arguments: (self, name)
338. **integration_system\transformer.py** (Line 326)
   - Arguments: (self, name)
339. **integration_system\transformer.py** (Line 374)
   - Arguments: (self)
340. **integration_system\versioning.py** (Line 26)
   - Arguments: (self, version, description, compatibility, deprecated)
341. **integration_system\versioning.py** (Line 57)
   - Arguments: (self)
342. **integration_system\webhooks_integration.py** (Line 38)
   - Arguments: (self)
343. **integration_system\webhooks_integration.py** (Line 378)
   - Arguments: (self)
344. **services\IncidentService.py** (Line 31)
   - Arguments: (self)
345. **services\PasswordHistoryService.py** (Line 42)
   - Arguments: (self)
346. **services\SecurityInsightService.py** (Line 43)
   - Arguments: (self)
347. **services\SecurityPolicyService.py** (Line 42)
   - Arguments: (self)
348. **services\ThreatIntelService.py** (Line 34)
   - Arguments: (self)
349. **services\TrustedDeviceService.py** (Line 42)
   - Arguments: (self)
350. **utils\cache_manager.py** (Line 703)
   - Arguments: (self, user_id)
351. **utils\device.py** (Line 319)
   - Arguments: (self, user)
352. **utils\device.py** (Line 891)
   - Arguments: (self, request)

### __new__

1. **services\PasswordHistoryService.py** (Line 30)
   - Arguments: (cls)
2. **services\SecurityInsightService.py** (Line 31)
   - Arguments: (cls)
3. **services\SecurityPolicyService.py** (Line 30)
   - Arguments: (cls)
4. **services\TrustedDeviceService.py** (Line 30)
   - Arguments: (cls)

### __post_init__

1. **endpoint.py** (Line 69)
   - Arguments: (self)
2. **registry.py** (Line 60)
   - Arguments: (self)
3. **resources.py** (Line 68)
   - Arguments: (self)

### __str__

1. **abstracts.py** (Line 31)
   - Arguments: (self)
2. **abstracts.py** (Line 68)
   - Arguments: (self)
3. **abstracts.py** (Line 80)
   - Arguments: (self)
4. **events.py** (Line 52)
   - Arguments: (self)
5. **exceptions.py** (Line 85)
   - Arguments: (self)
6. **feature_flags.py** (Line 100)
   - Arguments: (self)
7. **models.py** (Line 224)
   - Arguments: (self)
8. **models.py** (Line 762)
   - Arguments: (self)
9. **models.py** (Line 1163)
   - Arguments: (self)
10. **models.py** (Line 1319)
   - Arguments: (self)
11. **models.py** (Line 1402)
   - Arguments: (self)
12. **models.py** (Line 1497)
   - Arguments: (self)
13. **models.py** (Line 1603)
   - Arguments: (self)
14. **models.py** (Line 1778)
   - Arguments: (self)
15. **models.py** (Line 1879)
   - Arguments: (self)
16. **models.py** (Line 1961)
   - Arguments: (self)
17. **models.py** (Line 2029)
   - Arguments: (self)
18. **models.py** (Line 2170)
   - Arguments: (self)
19. **models.py** (Line 2269)
   - Arguments: (self)
20. **models.py** (Line 2408)
   - Arguments: (self)
21. **models.py** (Line 2457)
   - Arguments: (self)
22. **models.py** (Line 2591)
   - Arguments: (self)
23. **models.py** (Line 2632)
   - Arguments: (self)
24. **models.py** (Line 2720)
   - Arguments: (self)
25. **models.py** (Line 2823)
   - Arguments: (self)
26. **models.py** (Line 2865)
   - Arguments: (self)
27. **models.py** (Line 2955)
   - Arguments: (self)
28. **models.py** (Line 2983)
   - Arguments: (self)
29. **models.py** (Line 3391)
   - Arguments: (self)
30. **models.py** (Line 3844)
   - Arguments: (self)
31. **models.py** (Line 5391)
   - Arguments: (self)
32. **models.py** (Line 5982)
   - Arguments: (self)
33. **models.py** (Line 6377)
   - Arguments: (self)
34. **models.py** (Line 7165)
   - Arguments: (self)
35. **models.py** (Line 8105)
   - Arguments: (self)
36. **models.py** (Line 8190)
   - Arguments: (self)
37. **models.py** (Line 8282)
   - Arguments: (self)
38. **models.py** (Line 8379)
   - Arguments: (self)
39. **models.py** (Line 8432)
   - Arguments: (self)
40. **models.py** (Line 8495)
   - Arguments: (self)
41. **models.py** (Line 8592)
   - Arguments: (self)
42. **notifications_push.py** (Line 121)
   - Arguments: (self)
43. **notifications_push.py** (Line 186)
   - Arguments: (self)
44. **sanctions.py** (Line 129)
   - Arguments: (self)
45. **sanctions.py** (Line 272)
   - Arguments: (self)
46. **webhooks.py** (Line 109)
   - Arguments: (self)
47. **webhooks.py** (Line 213)
   - Arguments: (self)
48. **integration_system\versioning.py** (Line 50)
   - Arguments: (self)

### active

1. **managers.py** (Line 276)
   - Arguments: (self)
2. **managers.py** (Line 575)
   - Arguments: (self)
3. **managers.py** (Line 658)
   - Arguments: (self)
4. **querysets.py** (Line 24)
   - Arguments: (self)
5. **querysets.py** (Line 463)
   - Arguments: (self)
6. **querysets.py** (Line 550)
   - Arguments: (self)

### add_alert_handler

1. **monitoring.py** (Line 86)
   - Arguments: (self, handler)
2. **monitoring.py** (Line 623)
   - Arguments: (self, handler)

### add_arguments

1. **management\commands\block_suspicious_ips.py** (Line 32)
   - Arguments: (self, parser)
2. **management\commands\export_security_report.py** (Line 35)
   - Arguments: (self, parser)
3. **management\commands\run_security_scan.py** (Line 34)
   - Arguments: (self, parser)
4. **management\commands\seed_security_rules.py** (Line 31)
   - Arguments: (self, parser)
5. **management\commands\unlock_user_accounts.py** (Line 31)
   - Arguments: (self, parser)

### add_global_transformation

1. **integration_system\bridge.py** (Line 386)
   - Arguments: (self, transformation_name, transformation_func)
2. **integration_system\transformer.py** (Line 438)
   - Arguments: (self, transformation_name, transformation)

### add_ip_to_whitelist

1. **models.py** (Line 7867)
   - Arguments: (self, ip_address)
2. **views.py** (Line 8309)
   - Arguments: (self, request, pk)

### add_rule

1. **abstracts.py** (Line 519)
   - Arguments: (self, rule_name, rule_config)
2. **integration_system\data_validator.py** (Line 251)
   - Arguments: (self, rule)

### add_to_blacklist

1. **models.py** (Line 7903)
   - Arguments: (self, destination, reason)
2. **views.py** (Line 8375)
   - Arguments: (self, request, pk)

### add_transformation

1. **integration_system\bridge.py** (Line 67)
   - Arguments: (self, transformation_name, transformation_func)
2. **integration_system\integ_adapter.py** (Line 161)
   - Arguments: (self, field, transformation)
3. **integration_system\transformer.py** (Line 47)
   - Arguments: (self, field, transformation)

### aggregate_by_severity

1. **querysets.py** (Line 189)
   - Arguments: (self)
2. **querysets.py** (Line 533)
   - Arguments: (self)

### aggregate_by_type

1. **querysets.py** (Line 185)
   - Arguments: (self)
2. **querysets.py** (Line 429)
   - Arguments: (self)
3. **querysets.py** (Line 525)
   - Arguments: (self)

### all

1. **admin.py** (Line 6659)
   - Arguments: (self)
2. **repositories.py** (Line 114)
   - Arguments: (self)

### allow_request

1. **throttling.py** (Line 90)
   - Arguments: (self, request, view)
2. **throttling.py** (Line 195)
   - Arguments: (self, request, view)
3. **throttling.py** (Line 246)
   - Arguments: (self, request, view)
4. **throttling.py** (Line 318)
   - Arguments: (self, request, view)
5. **throttling.py** (Line 337)
   - Arguments: (self, request, view)
6. **throttling.py** (Line 370)
   - Arguments: (self, request, view)
7. **throttling.py** (Line 410)
   - Arguments: (self, request, view)
8. **throttling.py** (Line 430)
   - Arguments: (self, request, view)

### analyze

1. **abstracts.py** (Line 146)
   - Arguments: (self, data)
2. **plugins.py** (Line 94)
   - Arguments: (self, data)
3. **plugins.py** (Line 471)
   - Arguments: (self, data)
4. **plugins.py** (Line 519)
   - Arguments: (self, data)

### apply_to_viewset

1. **viewset_cap.py** (Line 31)
   - Arguments: (self, viewset_class)
2. **viewset_cap.py** (Line 43)
   - Arguments: (self, viewset_class)
3. **viewset_cap.py** (Line 144)
   - Arguments: (self, viewset_class)
4. **viewset_cap.py** (Line 269)
   - Arguments: (self, viewset_class)
5. **viewset_cap.py** (Line 390)
   - Arguments: (self, viewset_class)
6. **viewset_cap.py** (Line 551)
   - Arguments: (self, viewset_class)

### assertSafeResponse

1. **tests.py** (Line 219)
   - Arguments: (self, response, expected_status)
2. **tests.py** (Line 423)
   - Arguments: (self, response, expected_status)

### assess_risk

1. **models.py** (Line 2084)
   - Arguments: (self)
2. **views.py** (Line 9196)
   - Arguments: (self, request, pk)

### assign_incident

1. **repositories.py** (Line 376)
   - Arguments: (self, incident_id, assigned_to)
2. **services\IncidentService.py** (Line 549)
   - Arguments: (self, incident_id, assigned_to, assigned_by, team)

### audit_action

1. **decorators.py** (Line 442)
   - Arguments: (action_type, log_level)
2. **decorators.py** (Line 635)
   - Arguments: (action_type, log_errors, default_response)

### authenticate

1. **plugins.py** (Line 80)
   - Arguments: (self, request, credentials)
2. **plugins.py** (Line 375)
   - Arguments: (self, request, credentials)
3. **plugins.py** (Line 418)
   - Arguments: (self, request, credentials)

### authorize

1. **plugins.py** (Line 85)
   - Arguments: (self, user, resource, action)
2. **plugins.py** (Line 392)
   - Arguments: (self, user, resource, action)
3. **plugins.py** (Line 429)
   - Arguments: (self, user, resource, action)

### ban_user

1. **repositories.py** (Line 546)
   - Arguments: (self, user, reason, expires_at, banned_by, metadata)
2. **repositories.py** (Line 685)
   - Arguments: (self)

### bulk_create

1. **repositories.py** (Line 82)
   - Arguments: (self, objects)
2. **viewset_cap.py** (Line 47)
   - Arguments: (self, request)

### bulk_deactivate

1. **views.py** (Line 5426)
   - Arguments: (self, request)
2. **views.py** (Line 6226)
   - Arguments: (self, request)

### bulk_delete

1. **repositories.py** (Line 98)
   - Arguments: (self, ids)
2. **viewset_cap.py** (Line 108)
   - Arguments: (self, request)

### bulk_update

1. **repositories.py** (Line 90)
   - Arguments: (self, objects, fields)
2. **views.py** (Line 1601)
   - Arguments: (self, request)
3. **viewset_cap.py** (Line 70)
   - Arguments: (self, request)

### by_date_range

1. **managers.py** (Line 44)
   - Arguments: (self, start_date, end_date)
2. **managers.py** (Line 219)
   - Arguments: (self, start_date, end_date)
3. **managers.py** (Line 738)
   - Arguments: (self, start_date, end_date)
4. **querysets.py** (Line 75)
   - Arguments: (self, start_date, end_date)

### by_fingerprint

1. **managers.py** (Line 436)
   - Arguments: (self, fingerprint)
2. **querysets.py** (Line 279)
   - Arguments: (self, fingerprint)

### by_ip

1. **managers.py** (Line 32)
   - Arguments: (self, ip_address)
2. **managers.py** (Line 296)
   - Arguments: (self, ip_address)
3. **managers.py** (Line 404)
   - Arguments: (self, ip_address)
4. **managers.py** (Line 838)
   - Arguments: (self, ip_address)
5. **querysets.py** (Line 53)
   - Arguments: (self, ip_address)

### by_ip_range

1. **managers.py** (Line 300)
   - Arguments: (self, ip_network)
2. **querysets.py** (Line 283)
   - Arguments: (self, ip_start, ip_end)
3. **querysets.py** (Line 507)
   - Arguments: (self, ip_range)

### by_priority

1. **managers.py** (Line 682)
   - Arguments: (self, priority)
2. **querysets.py** (Line 360)
   - Arguments: (self, priority)

### by_reason

1. **managers.py** (Line 599)
   - Arguments: (self, reason)
2. **querysets.py** (Line 569)
   - Arguments: (self, reason)

### by_risk_score_range

1. **querysets.py** (Line 143)
   - Arguments: (self, min_score, max_score)
2. **querysets.py** (Line 251)
   - Arguments: (self, min_score, max_score)

### by_severity

1. **managers.py** (Line 40)
   - Arguments: (self, severity)
2. **managers.py** (Line 183)
   - Arguments: (self, severity)
3. **querysets.py** (Line 59)
   - Arguments: (self, severity)
4. **querysets.py** (Line 493)
   - Arguments: (self, severity)

### by_source

1. **managers.py** (Line 292)
   - Arguments: (self, source)
2. **querysets.py** (Line 477)
   - Arguments: (self, source)

### by_type

1. **managers.py** (Line 187)
   - Arguments: (self, incident_type)
2. **managers.py** (Line 288)
   - Arguments: (self, blacklist_type)
3. **managers.py** (Line 396)
   - Arguments: (self, device_type)
4. **managers.py** (Line 595)
   - Arguments: (self, ban_type)
5. **managers.py** (Line 670)
   - Arguments: (self, policy_type)

### by_user

1. **managers.py** (Line 28)
   - Arguments: (self, user)
2. **managers.py** (Line 392)
   - Arguments: (self, user)
3. **managers.py** (Line 486)
   - Arguments: (self, user)
4. **managers.py** (Line 587)
   - Arguments: (self, user)
5. **managers.py** (Line 825)
   - Arguments: (self, user)
6. **querysets.py** (Line 43)
   - Arguments: (self, user)

### cache_response

1. **decorators.py** (Line 990)
   - Arguments: (timeout, key_func, vary_on_headers)
2. **views.py** (Line 482)
   - Arguments: (timeout)

### cache_result

1. **admin.py** (Line 6743)
   - Arguments: (timeout)
2. **caching.py** (Line 608)
   - Arguments: (key_pattern, ttl, cache_instance)
3. **common_imports.py** (Line 250)
   - Arguments: (timeout)
4. **models.py** (Line 118)
   - Arguments: (timeout)
5. **serializers.py** (Line 3667)
   - Arguments: (timeout)

### calculate_risk_level

1. **models.py** (Line 4617)
   - Arguments: (score)
2. **model_mixins.py** (Line 159)
   - Arguments: (self)
3. **serializers.py** (Line 6692)
   - Arguments: (score)
4. **views.py** (Line 6823)
   - Arguments: (score)

### calculate_risk_score

1. **models.py** (Line 8617)
   - Arguments: (self)
2. **utils.py** (Line 142)
   - Arguments: (factors)
3. **utils\security_helpers.py** (Line 294)
   - Arguments: (total_events, critical_count, high_count, medium_count, low_count)

### can_execute

1. **hooks.py** (Line 41)
   - Arguments: (self, context)
2. **tasks_cap.py** (Line 67)
   - Arguments: (self)
3. **integration_system\fallback_logic.py** (Line 40)
   - Arguments: (self, context)
4. **integration_system\health_check.py** (Line 43)
   - Arguments: (self)

### can_handle

1. **abstracts.py** (Line 423)
   - Arguments: (self, event)
2. **integration_system\event_bus.py** (Line 91)
   - Arguments: (self, message)

### can_retry

1. **integration_system\event_bus.py** (Line 68)
   - Arguments: (self)
2. **integration_system\message_queue.py** (Line 72)
   - Arguments: (self)

### check

1. **monitoring.py** (Line 90)
   - Arguments: (self)
2. **monitoring.py** (Line 174)
   - Arguments: (self)
3. **monitoring.py** (Line 331)
   - Arguments: (self)
4. **monitoring.py** (Line 488)
   - Arguments: (self)

### check_ip

1. **views.py** (Line 6068)
   - Arguments: (self, request)
2. **views.py** (Line 9261)
   - Arguments: (self, request, pk)
3. **tests\test_threat_intel.py** (Line 840)

### check_ip_reputation

1. **dependencies.py** (Line 166)
   - Arguments: (self, ip_address)
2. **dependencies.py** (Line 717)
   - Arguments: (self, ip_address)
3. **services\ThreatIntelService.py** (Line 86)
   - Arguments: (self, ip_address, include_details)

### check_maintenance_mode

1. **decorators.py** (Line 188)
2. **serializers.py** (Line 247)

### check_password_reuse

1. **managers.py** (Line 846)
   - Arguments: (self, user, password_hash, history_limit)
2. **services\PasswordHistoryService.py** (Line 91)
   - Arguments: (self, user, new_password_hash, reuse_limit)

### check_rate_limit

1. **caching.py** (Line 369)
   - Arguments: (self, key, limit, window)
2. **services.py** (Line 352)
   - Arguments: (self, identifier, limit, window_seconds, strategy)
3. **views.py** (Line 4486)
   - Arguments: (self, request)
4. **integration_system\message_queue.py** (Line 491)
   - Arguments: (self, queue_name)

### check_self

1. **views.py** (Line 5324)
   - Arguments: (self, request)
2. **views.py** (Line 7251)
   - Arguments: (self, request)

### check_user

1. **views.py** (Line 5280)
   - Arguments: (self, request)
2. **views.py** (Line 7208)
   - Arguments: (self, request)

### check_vpn

1. **tests\test_vpn_detector.py** (Line 716)
   - Arguments: (ip)
2. **utils\device.py** (Line 44)
   - Arguments: (ip_address)

### clean

1. **forms.py** (Line 96)
   - Arguments: (self)
2. **forms.py** (Line 158)
   - Arguments: (self)
3. **forms.py** (Line 244)
   - Arguments: (self)
4. **forms.py** (Line 413)
   - Arguments: (self)
5. **models.py** (Line 293)
   - Arguments: (self)
6. **models.py** (Line 1405)
   - Arguments: (self)
7. **models.py** (Line 2724)
   - Arguments: (self)
8. **models.py** (Line 2869)
   - Arguments: (self)
9. **models.py** (Line 3211)
   - Arguments: (self)
10. **models.py** (Line 3607)
   - Arguments: (self)
11. **models.py** (Line 5010)
   - Arguments: (self)
12. **models.py** (Line 5551)
   - Arguments: (self)
13. **models.py** (Line 6147)
   - Arguments: (self)
14. **models.py** (Line 6613)
   - Arguments: (self)
15. **models.py** (Line 7498)
   - Arguments: (self)

### cleanup

1. **abstracts.py** (Line 103)
   - Arguments: (self)
2. **plugins.py** (Line 42)
   - Arguments: (self)
3. **plugins.py** (Line 371)
   - Arguments: (self)
4. **plugins.py** (Line 414)
   - Arguments: (self)
5. **plugins.py** (Line 467)
   - Arguments: (self)
6. **plugins.py** (Line 515)
   - Arguments: (self)
7. **plugins.py** (Line 552)
   - Arguments: (self)
8. **plugins.py** (Line 598)
   - Arguments: (self)
9. **plugins.py** (Line 635)
   - Arguments: (self)
10. **plugins.py** (Line 670)
   - Arguments: (self)
11. **plugins.py** (Line 711)
   - Arguments: (self)
12. **plugins.py** (Line 755)
   - Arguments: (self)
13. **resources.py** (Line 164)
   - Arguments: (self)
14. **views.py** (Line 5356)
   - Arguments: (self, request)
15. **views.py** (Line 6195)
   - Arguments: (self, request)
16. **integration_system\data_bridge.py** (Line 689)
   - Arguments: (self)
17. **integration_system\integ_handler.py** (Line 321)
   - Arguments: (self)
18. **integration_system\integ_registry.py** (Line 486)
   - Arguments: (self)
19. **integration_system\webhooks_integration.py** (Line 369)
   - Arguments: (self)

### cleanup_expired_bans

1. **managers.py** (Line 642)
   - Arguments: (self)
2. **models.py** (Line 3368)
   - Arguments: (cls)

### cleanup_old_logs

1. **repositories.py** (Line 207)
   - Arguments: (self, days)
2. **tasks_cap.py** (Line 732)
   - Arguments: (days_to_keep, dry_run)
3. **integration_system\integ_audit_logs.py** (Line 327)
   - Arguments: (self)

### clear

1. **abstracts.py** (Line 584)
   - Arguments: (self)
2. **caching.py** (Line 189)
   - Arguments: (self)
3. **integration_system\message_queue.py** (Line 302)
   - Arguments: (self)

### clear_all_metrics

1. **integration_system\performance_monitor.py** (Line 295)
   - Arguments: (self)
2. **integration_system\performance_monitor.py** (Line 486)
   - Arguments: (self)

### clear_cache

1. **registry.py** (Line 344)
   - Arguments: (self)
2. **viewset_cap.py** (Line 617)
   - Arguments: (self, request)

### clear_history

1. **integration_system\integ_signals.py** (Line 301)
   - Arguments: (self, signal_name)
2. **integration_system\sync_manager.py** (Line 547)
   - Arguments: (self)

### clear_queue

1. **integration_system\event_bus.py** (Line 392)
   - Arguments: (self)
2. **integration_system\integ_handler.py** (Line 287)
   - Arguments: (self)

### configure

1. **integration_system\data_bridge.py** (Line 42)
   - Arguments: (self, config)
2. **integration_system\fallback_logic.py** (Line 73)
   - Arguments: (self, config)
3. **integration_system\integ_adapter.py** (Line 36)
   - Arguments: (self, config)
4. **integration_system\integ_adapter.py** (Line 196)
   - Arguments: (self, config)
5. **integration_system\integ_handler.py** (Line 302)
   - Arguments: (self, config)
6. **integration_system\webhooks_integration.py** (Line 51)
   - Arguments: (self, config)

### connect

1. **integration_system\bridge.py** (Line 94)
   - Arguments: (self)
2. **integration_system\integ_adapter.py** (Line 40)
   - Arguments: (self)
3. **integration_system\integ_adapter.py** (Line 204)
   - Arguments: (self)
4. **integration_system\integ_adapter.py** (Line 300)
   - Arguments: (self)
5. **integration_system\integ_adapter.py** (Line 411)
   - Arguments: (self)

### count

1. **admin.py** (Line 6657)
   - Arguments: (self)
2. **repositories.py** (Line 106)
   - Arguments: (self)
3. **selectors.py** (Line 62)
   - Arguments: (self)

### create

1. **abstracts.py** (Line 315)
   - Arguments: (self, data)
2. **repositories.py** (Line 44)
   - Arguments: (self)
3. **serializers.py** (Line 3445)
   - Arguments: (self, validated_data)
4. **serializers.py** (Line 4432)
   - Arguments: (self, validated_data)
5. **serializers.py** (Line 4603)
   - Arguments: (self, validated_data)
6. **serializers.py** (Line 5035)
   - Arguments: (self, validated_data)
7. **serializers.py** (Line 5258)
   - Arguments: (self, validated_data)
8. **serializers.py** (Line 5544)
   - Arguments: (self, validated_data)
9. **serializers.py** (Line 5857)
   - Arguments: (self, validated_data)
10. **serializers.py** (Line 6254)
   - Arguments: (self, validated_data)
11. **serializers.py** (Line 6599)
   - Arguments: (self, validated_data)
12. **serializers.py** (Line 7003)
   - Arguments: (self, validated_data)
13. **serializers.py** (Line 7268)
   - Arguments: (self, validated_data)
14. **serializers.py** (Line 7474)
   - Arguments: (self, validated_data)
15. **serializers.py** (Line 7953)
   - Arguments: (self, validated_data)
16. **serializers.py** (Line 9328)
   - Arguments: (self, validated_data)
17. **serializers.py** (Line 10128)
   - Arguments: (self, validated_data)
18. **serializers.py** (Line 10862)
   - Arguments: (self, validated_data)
19. **serializers.py** (Line 11508)
   - Arguments: (self, validated_data)
20. **views.py** (Line 854)
   - Arguments: (self, request)
21. **views.py** (Line 4195)
   - Arguments: (self, request)
22. **views.py** (Line 5190)
   - Arguments: (self, request)
23. **views.py** (Line 5938)
   - Arguments: (self, request)
24. **views.py** (Line 6986)
   - Arguments: (self, request)
25. **views.py** (Line 8996)
   - Arguments: (self, request)
26. **viewset.py** (Line 260)
   - Arguments: (self, request)

### create_custom_permission

1. **permissions.py** (Line 348)
   - Arguments: (check_func, message)
2. **permissions_backup.py** (Line 573)

### create_device

1. **repositories.py** (Line 266)
   - Arguments: (self, user, device_info)
2. **tests.py** (Line 1178)
   - Arguments: (i)

### create_incident

1. **repositories.py** (Line 359)
   - Arguments: (self, title, incident_type, description, severity, priority, user, affected_systems, assigned_to, metadata)
2. **repositories.py** (Line 681)
   - Arguments: (self)

### create_policy

1. **sanctions.py** (Line 557)
   - Arguments: (self, name, description, violation_types, severity_threshold, sanction_type)
2. **services\SecurityPolicyService.py** (Line 132)
   - Arguments: (self, tenant, policy_key, policy_name, policy_type, value, description, is_mandatory, priority, validation_rules, created_by)

### create_security_permission

1. **permissions.py** (Line 343)
   - Arguments: (permission)
2. **permissions_backup.py** (Line 552)
   - Arguments: (min_level)

### create_threat

1. **repositories.py** (Line 466)
   - Arguments: (self, threat_type, indicator, indicator_type, confidence, severity, source, description, ip_range, expires_at, metadata)
2. **repositories.py** (Line 689)
   - Arguments: (self)

### create_threat_intelligence

1. **exceptions.py** (Line 495)
   - Arguments: (message)
2. **factories_backup.py** (Line 430)
   - Arguments: (threat_count)

### created_by_display

1. **admin.py** (Line 2870)
   - Arguments: (self, obj)
2. **admin.py** (Line 6288)
   - Arguments: (self, obj)

### created_display

1. **admin.py** (Line 993)
   - Arguments: (self, obj)
2. **admin.py** (Line 1394)
   - Arguments: (self, obj)
3. **admin.py** (Line 2881)
   - Arguments: (self, obj)
4. **admin.py** (Line 3308)
   - Arguments: (self, obj)
5. **admin.py** (Line 5417)
   - Arguments: (self, obj)

### critical

1. **managers.py** (Line 203)
   - Arguments: (self)
2. **querysets.py** (Line 366)
   - Arguments: (self)

### deactivate

1. **views.py** (Line 5207)
   - Arguments: (self, request, pk)
2. **views.py** (Line 5960)
   - Arguments: (self, request, pk)

### decorator

1. **admin.py** (Line 71)
   - Arguments: (func)
2. **admin.py** (Line 87)
   - Arguments: (func)
3. **admin.py** (Line 6745)
   - Arguments: (func)
4. **caching.py** (Line 610)
   - Arguments: (func)
5. **common_imports.py** (Line 237)
   - Arguments: (func)
6. **common_imports.py** (Line 252)
   - Arguments: (func)
7. **common_imports.py** (Line 266)
   - Arguments: (func)
8. **decorators.py** (Line 34)
   - Arguments: (view_func)
9. **decorators.py** (Line 72)
   - Arguments: (view_func)
10. **decorators.py** (Line 128)
   - Arguments: (view_func)
11. **decorators.py** (Line 192)
   - Arguments: (view_func)
12. **decorators.py** (Line 220)
   - Arguments: (view_func)
13. **decorators.py** (Line 271)
   - Arguments: (view_func)
14. **decorators.py** (Line 400)
   - Arguments: (func)
15. **decorators.py** (Line 446)
   - Arguments: (func)
16. **decorators.py** (Line 490)
   - Arguments: (func)
17. **decorators.py** (Line 534)
   - Arguments: (func)
18. **decorators.py** (Line 552)
   - Arguments: (func)
19. **decorators.py** (Line 588)
   - Arguments: (func)
20. **decorators.py** (Line 647)
   - Arguments: (func)
21. **decorators.py** (Line 784)
   - Arguments: (func)
22. **decorators.py** (Line 907)
   - Arguments: (func)
23. **decorators.py** (Line 997)
   - Arguments: (func)
24. **decorators.py** (Line 1080)
   - Arguments: (func)
25. **decorators.py** (Line 1317)
   - Arguments: (func)
26. **decorators.py** (Line 1390)
   - Arguments: (func)
27. **endpoint.py** (Line 449)
   - Arguments: (func_or_class)
28. **feature_flags.py** (Line 701)
   - Arguments: (func)
29. **models.py** (Line 120)
   - Arguments: (func)
30. **models.py** (Line 107)
   - Arguments: (func)
31. **permissions.py** (Line 408)
   - Arguments: (view_func)
32. **permissions.py** (Line 425)
   - Arguments: (view_func)
33. **permissions_backup.py** (Line 619)
   - Arguments: (view_func)
34. **permissions_backup.py** (Line 641)
   - Arguments: (view_func)
35. **registry.py** (Line 401)
   - Arguments: (component_class)
36. **serializers.py** (Line 96)
   - Arguments: (view_func)
37. **serializers.py** (Line 133)
   - Arguments: (view_func)
38. **serializers.py** (Line 188)
   - Arguments: (view_func)
39. **serializers.py** (Line 251)
   - Arguments: (view_func)
40. **serializers.py** (Line 278)
   - Arguments: (view_func)
41. **serializers.py** (Line 3655)
   - Arguments: (func)
42. **serializers.py** (Line 3669)
   - Arguments: (func)
43. **serializers.py** (Line 3760)
   - Arguments: (func)
44. **tests.py** (Line 277)
   - Arguments: (func)
45. **throttling.py** (Line 621)
   - Arguments: (view_func)
46. **views.py** (Line 297)
   - Arguments: (func)
47. **views.py** (Line 333)
   - Arguments: (func)
48. **views.py** (Line 423)
   - Arguments: (func)
49. **views.py** (Line 453)
   - Arguments: (func)
50. **views.py** (Line 484)
   - Arguments: (func)
51. **viewset_cap.py** (Line 687)
   - Arguments: (viewset_class)
52. **integration_system\integ_signals.py** (Line 321)
   - Arguments: (func)
53. **utils\cache_manager.py** (Line 332)
   - Arguments: (func)
54. **utils\cache_manager.py** (Line 436)
   - Arguments: (func)
55. **utils\cache_manager.py** (Line 625)
   - Arguments: (func)
56. **utils\device.py** (Line 752)
   - Arguments: (func)
57. **utils\device.py** (Line 823)
   - Arguments: (func)

### decrypt

1. **encryption.py** (Line 225)
   - Arguments: (self, ciphertext, iv, tag)
2. **encryption.py** (Line 336)
   - Arguments: (self, ciphertext)

### decrypt_data

1. **plugins.py** (Line 113)
   - Arguments: (self, encrypted_data, key)
2. **plugins.py** (Line 562)
   - Arguments: (self, encrypted_data, key)
3. **plugins.py** (Line 608)
   - Arguments: (self, encrypted_data, key)

### decrypt_sensitive_data

1. **encryption.py** (Line 477)
   - Arguments: (self, encrypted_data)
2. **utils.py** (Line 70)
   - Arguments: (encrypted_data, key)

### delete

1. **abstracts.py** (Line 330)
   - Arguments: (self, id)
2. **abstracts.py** (Line 579)
   - Arguments: (self, key)
3. **caching.py** (Line 122)
   - Arguments: (self, key)
4. **mixins.py** (Line 53)
   - Arguments: (self)
5. **repositories.py** (Line 69)
   - Arguments: (self, id)
6. **serializers.py** (Line 673)
   - Arguments: (self, request)
7. **utils\cache_manager.py** (Line 169)
   - Arguments: (key)

### destroy

1. **views.py** (Line 1092)
   - Arguments: (self, request)
2. **viewset.py** (Line 272)
   - Arguments: (self, request)

### device_display

1. **admin.py** (Line 1753)
   - Arguments: (self, obj)
2. **admin.py** (Line 4026)
   - Arguments: (self, obj)

### device_info_display

1. **admin.py** (Line 969)
   - Arguments: (self, obj)
2. **admin.py** (Line 3452)
   - Arguments: (self, obj)

### disable

1. **abstracts.py** (Line 182)
   - Arguments: (self)
2. **abstracts.py** (Line 431)
   - Arguments: (self)
3. **abstracts.py** (Line 462)
   - Arguments: (self)
4. **abstracts.py** (Line 515)
   - Arguments: (self)
5. **events.py** (Line 431)
   - Arguments: (self)
6. **hooks.py** (Line 72)
   - Arguments: (self)
7. **plugins.py** (Line 71)
   - Arguments: (self)
8. **serializers.py** (Line 2674)
   - Arguments: (self, request)
9. **signals_cap.py** (Line 278)
   - Arguments: (self)
10. **signals_cap.py** (Line 530)
   - Arguments: (self)
11. **tasks_cap.py** (Line 59)
   - Arguments: (self)
12. **integration_system\auth_bridge.py** (Line 547)
   - Arguments: (self)
13. **integration_system\bridge.py** (Line 280)
   - Arguments: (self)
14. **integration_system\bridge.py** (Line 448)
   - Arguments: (self)
15. **integration_system\circuit_breaker.py** (Line 299)
   - Arguments: (self)
16. **integration_system\data_validator.py** (Line 47)
   - Arguments: (self)
17. **integration_system\data_validator.py** (Line 389)
   - Arguments: (self)
18. **integration_system\data_validator.py** (Line 551)
   - Arguments: (self)
19. **integration_system\event_bus.py** (Line 139)
   - Arguments: (self)
20. **integration_system\event_bus.py** (Line 387)
   - Arguments: (self)
21. **integration_system\event_bus.py** (Line 504)
   - Arguments: (self)
22. **integration_system\fallback_logic.py** (Line 85)
   - Arguments: (self)
23. **integration_system\fallback_logic.py** (Line 483)
   - Arguments: (self)
24. **integration_system\fallback_logic.py** (Line 550)
   - Arguments: (self)
25. **integration_system\health_check.py** (Line 143)
   - Arguments: (self)
26. **integration_system\health_check.py** (Line 638)
   - Arguments: (self)
27. **integration_system\integ_adapter.py** (Line 169)
   - Arguments: (self)
28. **integration_system\integ_audit_logs.py** (Line 355)
   - Arguments: (self)
29. **integration_system\integ_audit_logs.py** (Line 508)
   - Arguments: (self)
30. **integration_system\integ_exceptions.py** (Line 454)
   - Arguments: (self)
31. **integration_system\integ_registry.py** (Line 481)
   - Arguments: (self)
32. **integration_system\integ_signals.py** (Line 296)
   - Arguments: (self)
33. **integration_system\message_queue.py** (Line 297)
   - Arguments: (self)
34. **integration_system\message_queue.py** (Line 441)
   - Arguments: (self)
35. **integration_system\performance_monitor.py** (Line 290)
   - Arguments: (self)
36. **integration_system\performance_monitor.py** (Line 496)
   - Arguments: (self)
37. **integration_system\sync_manager.py** (Line 45)
   - Arguments: (self)
38. **integration_system\sync_manager.py** (Line 542)
   - Arguments: (self)
39. **integration_system\transformer.py** (Line 109)
   - Arguments: (self)
40. **integration_system\transformer.py** (Line 484)
   - Arguments: (self)
41. **integration_system\versioning.py** (Line 248)
   - Arguments: (self)

### disable_all_strategies

1. **integration_system\fallback_logic.py** (Line 463)
   - Arguments: (self)
2. **integration_system\sync_manager.py** (Line 532)
   - Arguments: (self)

### disconnect

1. **integration_system\bridge.py** (Line 135)
   - Arguments: (self)
2. **integration_system\integ_adapter.py** (Line 53)
   - Arguments: (self)
3. **integration_system\integ_adapter.py** (Line 243)
   - Arguments: (self)
4. **integration_system\integ_adapter.py** (Line 321)
   - Arguments: (self)
5. **integration_system\integ_adapter.py** (Line 432)
   - Arguments: (self)

### dispatch

1. **mixins.py** (Line 146)
   - Arguments: (self, request)
2. **mixins.py** (Line 184)
   - Arguments: (self, request)
3. **mixins.py** (Line 206)
   - Arguments: (self, request)
4. **mixins.py** (Line 281)
   - Arguments: (self, request)
5. **mixins.py** (Line 365)
   - Arguments: (self, request)
6. **mixins.py** (Line 424)
   - Arguments: (self, request)
7. **serializers.py** (Line 329)
   - Arguments: (self, request)

### duration_display

1. **admin.py** (Line 2090)
   - Arguments: (self, obj)
2. **admin.py** (Line 4494)
   - Arguments: (self, obj)

### enable

1. **abstracts.py** (Line 178)
   - Arguments: (self)
2. **abstracts.py** (Line 427)
   - Arguments: (self)
3. **abstracts.py** (Line 458)
   - Arguments: (self)
4. **abstracts.py** (Line 511)
   - Arguments: (self)
5. **events.py** (Line 426)
   - Arguments: (self)
6. **hooks.py** (Line 68)
   - Arguments: (self)
7. **plugins.py** (Line 67)
   - Arguments: (self)
8. **signals_cap.py** (Line 274)
   - Arguments: (self)
9. **signals_cap.py** (Line 526)
   - Arguments: (self)
10. **tasks_cap.py** (Line 55)
   - Arguments: (self)
11. **integration_system\auth_bridge.py** (Line 540)
   - Arguments: (self)
12. **integration_system\bridge.py** (Line 275)
   - Arguments: (self)
13. **integration_system\bridge.py** (Line 443)
   - Arguments: (self)
14. **integration_system\circuit_breaker.py** (Line 294)
   - Arguments: (self)
15. **integration_system\data_validator.py** (Line 43)
   - Arguments: (self)
16. **integration_system\data_validator.py** (Line 384)
   - Arguments: (self)
17. **integration_system\data_validator.py** (Line 546)
   - Arguments: (self)
18. **integration_system\event_bus.py** (Line 135)
   - Arguments: (self)
19. **integration_system\event_bus.py** (Line 382)
   - Arguments: (self)
20. **integration_system\event_bus.py** (Line 499)
   - Arguments: (self)
21. **integration_system\fallback_logic.py** (Line 81)
   - Arguments: (self)
22. **integration_system\fallback_logic.py** (Line 478)
   - Arguments: (self)
23. **integration_system\fallback_logic.py** (Line 545)
   - Arguments: (self)
24. **integration_system\health_check.py** (Line 139)
   - Arguments: (self)
25. **integration_system\health_check.py** (Line 633)
   - Arguments: (self)
26. **integration_system\integ_adapter.py** (Line 165)
   - Arguments: (self)
27. **integration_system\integ_audit_logs.py** (Line 350)
   - Arguments: (self)
28. **integration_system\integ_audit_logs.py** (Line 503)
   - Arguments: (self)
29. **integration_system\integ_exceptions.py** (Line 449)
   - Arguments: (self)
30. **integration_system\integ_registry.py** (Line 476)
   - Arguments: (self)
31. **integration_system\integ_signals.py** (Line 291)
   - Arguments: (self)
32. **integration_system\message_queue.py** (Line 292)
   - Arguments: (self)
33. **integration_system\message_queue.py** (Line 436)
   - Arguments: (self)
34. **integration_system\performance_monitor.py** (Line 285)
   - Arguments: (self)
35. **integration_system\performance_monitor.py** (Line 491)
   - Arguments: (self)
36. **integration_system\sync_manager.py** (Line 41)
   - Arguments: (self)
37. **integration_system\sync_manager.py** (Line 537)
   - Arguments: (self)
38. **integration_system\transformer.py** (Line 105)
   - Arguments: (self)
39. **integration_system\transformer.py** (Line 479)
   - Arguments: (self)
40. **integration_system\versioning.py** (Line 243)
   - Arguments: (self)

### enable_all_strategies

1. **integration_system\fallback_logic.py** (Line 458)
   - Arguments: (self)
2. **integration_system\sync_manager.py** (Line 527)
   - Arguments: (self)

### encrypt

1. **encryption.py** (Line 216)
   - Arguments: (self, plaintext)
2. **encryption.py** (Line 320)
   - Arguments: (self, plaintext)

### encrypt_data

1. **plugins.py** (Line 108)
   - Arguments: (self, data, key)
2. **plugins.py** (Line 556)
   - Arguments: (self, data, key)
3. **plugins.py** (Line 602)
   - Arguments: (self, data, key)

### encrypt_sensitive_data

1. **encryption.py** (Line 425)
   - Arguments: (self, data, algorithm)
2. **utils.py** (Line 56)
   - Arguments: (data, key)

### evaluate

1. **abstracts.py** (Line 502)
   - Arguments: (self, context)
2. **models.py** (Line 1166)
   - Arguments: (self, user, ip_address, device_info, activity_data)
3. **models.py** (Line 1781)
   - Arguments: (self, user_data, activity_data, device_data)

### execute

1. **abstracts.py** (Line 98)
   - Arguments: (self, context)
2. **abstracts.py** (Line 357)
   - Arguments: (self, context)
3. **hooks.py** (Line 37)
   - Arguments: (self, context)
4. **hooks.py** (Line 106)
   - Arguments: (self, context)
5. **hooks.py** (Line 183)
   - Arguments: (self, context)
6. **hooks.py** (Line 271)
   - Arguments: (self, context)
7. **hooks.py** (Line 364)
   - Arguments: (self, context)
8. **hooks.py** (Line 463)
   - Arguments: (self, context)
9. **interactors.py** (Line 36)
   - Arguments: (self)
10. **interactors.py** (Line 61)
   - Arguments: (self, analysis_request)
11. **interactors.py** (Line 202)
   - Arguments: (self, action_request)
12. **interactors.py** (Line 308)
   - Arguments: (self, monitoring_request)
13. **interactors.py** (Line 506)
   - Arguments: (self, security_request)
14. **interactors.py** (Line 713)
   - Arguments: (self, dashboard_request)
15. **plugins.py** (Line 37)
   - Arguments: (self, context)
16. **plugins.py** (Line 367)
   - Arguments: (self, context)
17. **plugins.py** (Line 410)
   - Arguments: (self, context)
18. **plugins.py** (Line 445)
   - Arguments: (self, context)
19. **plugins.py** (Line 491)
   - Arguments: (self, context)
20. **plugins.py** (Line 539)
   - Arguments: (self, context)
21. **plugins.py** (Line 585)
   - Arguments: (self, context)
22. **plugins.py** (Line 631)
   - Arguments: (self, context)
23. **plugins.py** (Line 666)
   - Arguments: (self, context)
24. **plugins.py** (Line 704)
   - Arguments: (self, context)
25. **plugins.py** (Line 748)
   - Arguments: (self, context)
26. **tasks_cap.py** (Line 43)
   - Arguments: (self)
27. **tasks_cap.py** (Line 82)
   - Arguments: (self, analysis_type, parameters)
28. **tasks_cap.py** (Line 293)
   - Arguments: (self, operation, parameters)
29. **tasks_cap.py** (Line 424)
   - Arguments: (self, notification_type, parameters)
30. **use_cases.py** (Line 32)
   - Arguments: (self)
31. **use_cases.py** (Line 56)
   - Arguments: (self, analysis_type, time_period)
32. **use_cases.py** (Line 313)
   - Arguments: (self, action, incident_id)
33. **use_cases.py** (Line 533)
   - Arguments: (self, action)
34. **use_cases.py** (Line 680)
   - Arguments: (self, action)
35. **integration_system\fallback_logic.py** (Line 69)
   - Arguments: (self, context)
36. **integration_system\fallback_logic.py** (Line 115)
   - Arguments: (self, context)
37. **integration_system\fallback_logic.py** (Line 170)
   - Arguments: (self, context)
38. **integration_system\fallback_logic.py** (Line 240)
   - Arguments: (self, context)
39. **integration_system\fallback_logic.py** (Line 298)
   - Arguments: (self, context)
40. **integration_system\fallback_logic.py** (Line 319)
   - Arguments: (self, context)

### execute_capability

1. **tasks_cap.py** (Line 726)
   - Arguments: (self, capability_name)
2. **tasks_cap.py** (Line 565)
   - Arguments: (self, capability_name)

### execute_check

1. **integration_system\health_check.py** (Line 39)
   - Arguments: (self)
2. **integration_system\health_check.py** (Line 155)
   - Arguments: (self)
3. **integration_system\health_check.py** (Line 221)
   - Arguments: (self)
4. **integration_system\health_check.py** (Line 300)
   - Arguments: (self)
5. **integration_system\health_check.py** (Line 364)
   - Arguments: (self)
6. **integration_system\health_check.py** (Line 434)
   - Arguments: (self)

### exists

1. **repositories.py** (Line 110)
   - Arguments: (self)
2. **selectors.py** (Line 66)
   - Arguments: (self)

### expired

1. **managers.py** (Line 280)
   - Arguments: (self)
2. **managers.py** (Line 502)
   - Arguments: (self)
3. **managers.py** (Line 579)
   - Arguments: (self)
4. **querysets.py** (Line 467)
   - Arguments: (self)
5. **querysets.py** (Line 554)
   - Arguments: (self)

### expiring_soon

1. **managers.py** (Line 323)
   - Arguments: (self, days)
2. **managers.py** (Line 608)
   - Arguments: (self, days)
3. **querysets.py** (Line 520)
   - Arguments: (self, days)

### export

1. **views.py** (Line 1660)
   - Arguments: (self, request)
2. **viewset_cap.py** (Line 148)
   - Arguments: (self, request)

### extend

1. **sanctions.py** (Line 186)
   - Arguments: (self, days, extended_by, reason)
2. **views.py** (Line 5238)
   - Arguments: (self, request, pk)
3. **views.py** (Line 5991)
   - Arguments: (self, request, pk)

### extract_device_info

1. **utils\device.py** (Line 238)
   - Arguments: (request)
2. **utils\security_helpers.py** (Line 59)
   - Arguments: (user_agent)

### filter

1. **abstracts.py** (Line 249)
   - Arguments: (self, data, criteria)
2. **admin.py** (Line 6658)
   - Arguments: (self)
3. **repositories.py** (Line 118)
   - Arguments: (self)
4. **signals_cap.py** (Line 522)
   - Arguments: (self, signal_record)
5. **signals_cap.py** (Line 549)
   - Arguments: (self, signal_record)
6. **signals_cap.py** (Line 567)
   - Arguments: (self, signal_record)

### filter_active

1. **selectors.py** (Line 36)
   - Arguments: (self)
2. **selectors.py** (Line 488)
   - Arguments: (self)
3. **selectors.py** (Line 596)
   - Arguments: (self)

### filter_by_ip_range

1. **selectors.py** (Line 274)
   - Arguments: (self, ip_start, ip_end)
2. **selectors.py** (Line 532)
   - Arguments: (self, ip_range)

### filter_by_risk_score_range

1. **selectors.py** (Line 108)
   - Arguments: (self, min_score, max_score)
2. **selectors.py** (Line 242)
   - Arguments: (self, min_score, max_score)

### filter_by_severity

1. **selectors.py** (Line 86)
   - Arguments: (self, severities)
2. **selectors.py** (Line 518)
   - Arguments: (self, severities)

### filter_by_user

1. **selectors.py** (Line 92)
   - Arguments: (self, user)
2. **selectors.py** (Line 208)
   - Arguments: (self, user)

### filter_expired

1. **selectors.py** (Line 492)
   - Arguments: (self)
2. **selectors.py** (Line 600)
   - Arguments: (self)

### filter_is_suspicious

1. **filters.py** (Line 95)
   - Arguments: (self, queryset, name, value)
2. **filters.py** (Line 251)
   - Arguments: (self, queryset, name, value)

### filter_user

1. **filters.py** (Line 84)
   - Arguments: (self, queryset, name, value)
2. **filters.py** (Line 302)
   - Arguments: (self, queryset, name, value)
3. **filters.py** (Line 446)
   - Arguments: (self, queryset, name, value)
4. **filters.py** (Line 482)
   - Arguments: (self, queryset, name, value)
5. **filters.py** (Line 521)
   - Arguments: (self, queryset, name, value)
6. **filters.py** (Line 568)
   - Arguments: (self, queryset, name, value)
7. **filters.py** (Line 629)
   - Arguments: (self, queryset, name, value)
8. **filters.py** (Line 698)
   - Arguments: (self, queryset, name, value)

### generate_backup_codes

1. **models.py** (Line 2880)
   - Arguments: (self, count)
2. **views.py** (Line 9560)
   - Arguments: (self, request, pk)

### generate_device_fingerprint

1. **utils.py** (Line 130)
   - Arguments: (user_agent, ip)
2. **utils\security_helpers.py** (Line 20)
   - Arguments: (user_agent, ip_address, screen_resolution, timezone_offset, language, platform)

### generate_key

1. **encryption.py** (Line 103)
   - Arguments: (self, algorithm)
2. **utils\cache_manager.py** (Line 36)
   - Arguments: (prefix)

### generate_report

1. **abstracts.py** (Line 199)
   - Arguments: (self, report_type, parameters)
2. **duplicate_analyzer.py** (Line 139)
   - Arguments: (self)
3. **plugins.py** (Line 141)
   - Arguments: (self, report_type, parameters)
4. **plugins.py** (Line 715)
   - Arguments: (self, report_type, parameters)
5. **plugins.py** (Line 759)
   - Arguments: (self, report_type, parameters)

### generate_secure_token

1. **common_imports.py** (Line 204)
   - Arguments: (length)
2. **encryption.py** (Line 620)
   - Arguments: (self, length)
3. **utils.py** (Line 30)
   - Arguments: (length)

### generate_security_report

1. **tasks.py** (Line 211)
   - Arguments: (self)
2. **tasks_cap.py** (Line 742)
   - Arguments: (report_type, parameters)

### get

1. **abstracts.py** (Line 569)
   - Arguments: (self, key)
2. **caching.py** (Line 89)
   - Arguments: (self, key, default)
3. **endpoint.py** (Line 551)
   - Arguments: (self, request)
4. **serializers.py** (Line 503)
   - Arguments: (self, request)
5. **serializers.py** (Line 734)
   - Arguments: (self, request)
6. **serializers.py** (Line 913)
   - Arguments: (self, request)
7. **serializers.py** (Line 1078)
   - Arguments: (self, request)
8. **serializers.py** (Line 1373)
   - Arguments: (self, request)
9. **serializers.py** (Line 1558)
   - Arguments: (self, request)
10. **serializers.py** (Line 1728)
   - Arguments: (self, request)
11. **serializers.py** (Line 1833)
   - Arguments: (self, request)
12. **serializers.py** (Line 2023)
   - Arguments: (self, request)
13. **serializers.py** (Line 2122)
   - Arguments: (self, request)
14. **serializers.py** (Line 2212)
   - Arguments: (self, request)
15. **serializers.py** (Line 2313)
   - Arguments: (self, request)
16. **serializers.py** (Line 2428)
   - Arguments: (self, request)
17. **serializers.py** (Line 2726)
   - Arguments: (self, request)
18. **views.py** (Line 2805)
   - Arguments: (self, request)
19. **views.py** (Line 2956)
   - Arguments: (self, request)
20. **views.py** (Line 3179)
   - Arguments: (self, request)
21. **views.py** (Line 4748)
   - Arguments: (self, request)
22. **views.py** (Line 5496)
   - Arguments: (self, request)
23. **views.py** (Line 6496)
   - Arguments: (self, request)
24. **views.py** (Line 7443)
   - Arguments: (self, request)
25. **views.py** (Line 7594)
   - Arguments: (self, request)
26. **views.py** (Line 8063)
   - Arguments: (self, request)
27. **views.py** (Line 8570)
   - Arguments: (self, request)
28. **views.py** (Line 8832)
   - Arguments: (self, request)
29. **views.py** (Line 9598)
   - Arguments: (self, request)
30. **views.py** (Line 9658)
   - Arguments: (self, request)
31. **views.py** (Line 9806)
   - Arguments: (self, request)
32. **utils\cache_manager.py** (Line 98)
   - Arguments: (key, default)

### get_active_bans

1. **models.py** (Line 3341)
   - Arguments: (cls, user_id)
2. **repositories.py** (Line 518)
   - Arguments: (self)

### get_active_incidents

1. **context_processors.py** (Line 391)
2. **services\IncidentService.py** (Line 306)
   - Arguments: (self, severity, assigned_to, limit)

### get_active_threats

1. **context_processors.py** (Line 403)
2. **repositories.py** (Line 434)
   - Arguments: (self)
3. **services\ThreatIntelService.py** (Line 346)
   - Arguments: (self, threat_type, limit)

### get_all_statistics

1. **integration_system\data_validator.py** (Line 524)
   - Arguments: (self)
2. **integration_system\event_bus.py** (Line 477)
   - Arguments: (self)
3. **integration_system\fallback_logic.py** (Line 468)
   - Arguments: (self)
4. **integration_system\transformer.py** (Line 455)
   - Arguments: (self)

### get_all_status

1. **dependencies.py** (Line 694)
   - Arguments: (self)
2. **integration_system\bridge.py** (Line 366)
   - Arguments: (self)
3. **integration_system\circuit_breaker.py** (Line 233)
   - Arguments: (self)
4. **integration_system\integ_adapter.py** (Line 553)
   - Arguments: (self)
5. **integration_system\integ_handler.py** (Line 242)
   - Arguments: (self)
6. **integration_system\integ_registry.py** (Line 249)
   - Arguments: (self)
7. **integration_system\message_queue.py** (Line 410)
   - Arguments: (self)

### get_ban_statistics

1. **managers.py** (Line 627)
   - Arguments: (self)
2. **repositories.py** (Line 579)
   - Arguments: (self)

### get_by_id

1. **abstracts.py** (Line 320)
   - Arguments: (self, id)
2. **repositories.py** (Line 33)
   - Arguments: (self, id)
3. **selectors.py** (Line 25)
   - Arguments: (self, id)

### get_by_ids

1. **repositories.py** (Line 40)
   - Arguments: (self, ids)
2. **selectors.py** (Line 32)
   - Arguments: (self, ids)

### get_by_user

1. **repositories.py** (Line 142)
   - Arguments: (self, user)
2. **repositories.py** (Line 234)
   - Arguments: (self, user)

### get_cache_key

1. **models.py** (Line 2272)
   - Arguments: (self, identifier)
2. **pagination.py** (Line 91)
   - Arguments: (self)
3. **pagination.py** (Line 543)
   - Arguments: (self, request)
4. **throttling.py** (Line 75)
   - Arguments: (self, request, view)
5. **throttling.py** (Line 180)
   - Arguments: (self, request, view)
6. **throttling.py** (Line 241)
   - Arguments: (self, request, view)
7. **views.py** (Line 112)
   - Arguments: (self, request, view)

### get_choices

1. **choices.py** (Line 80)
   - Arguments: (cls)
2. **choices.py** (Line 129)
   - Arguments: (cls)
3. **choices.py** (Line 203)
   - Arguments: (cls)
4. **choices.py** (Line 278)
   - Arguments: (cls)
5. **choices.py** (Line 392)
   - Arguments: (cls)
6. **choices.py** (Line 420)
   - Arguments: (cls)
7. **choices.py** (Line 497)
   - Arguments: (cls)

### get_client_ip

1. **common_imports.py** (Line 195)
   - Arguments: (request)
2. **consumers.py** (Line 324)
   - Arguments: (self)
3. **models.py** (Line 4631)
   - Arguments: (request)
4. **permissions_backup.py** (Line 459)
   - Arguments: (self, request)
5. **serializers.py** (Line 3177)
   - Arguments: (request)
6. **serializers.py** (Line 410)
   - Arguments: (self, request)
7. **utils.py** (Line 275)
   - Arguments: (request)
8. **validators.py** (Line 664)
   - Arguments: (request)
9. **views.py** (Line 5033)
   - Arguments: (request)
10. **views.py** (Line 5756)
   - Arguments: (request)
11. **utils\device.py** (Line 15)
   - Arguments: (request)

### get_config_value

1. **dependencies.py** (Line 85)
   - Arguments: (self, key, default)
2. **models.py** (Line 5783)
   - Arguments: (self, key, default)

### get_dependencies

1. **registry.py** (Line 211)
   - Arguments: (self, name)
2. **tasks_cap.py** (Line 51)
   - Arguments: (self)

### get_device_statistics

1. **managers.py** (Line 444)
   - Arguments: (self)
2. **repositories.py** (Line 299)
   - Arguments: (self)
3. **services\TrustedDeviceService.py** (Line 287)
   - Arguments: (self, user_id)

### get_device_summary

1. **serializers.py** (Line 4712)
   - Arguments: (self, obj)
2. **serializers.py** (Line 10760)
   - Arguments: (self, obj)

### get_duration

1. **models.py** (Line 8308)
   - Arguments: (self)
2. **serializers.py** (Line 12010)
   - Arguments: (self, obj)

### get_effective_value

1. **models.py** (Line 8499)
   - Arguments: (self)
2. **serializers.py** (Line 12132)
   - Arguments: (self, obj)

### get_efficiency_rate

1. **serializers.py** (Line 9742)
   - Arguments: (self, obj)
2. **serializers.py** (Line 11122)
   - Arguments: (self, obj)

### get_error_rate

1. **serializers.py** (Line 9918)
   - Arguments: (self, obj)
2. **serializers.py** (Line 11298)
   - Arguments: (self, obj)

### get_event_breakdown

1. **models.py** (Line 8604)
   - Arguments: (self)
2. **serializers.py** (Line 12169)
   - Arguments: (self, obj)

### get_event_statistics

1. **events.py** (Line 386)
   - Arguments: (self)
2. **managers.py** (Line 94)
   - Arguments: (self, days)

### get_health_status

1. **serializers.py** (Line 9807)
   - Arguments: (self, obj)
2. **serializers.py** (Line 11187)
   - Arguments: (self, obj)

### get_hourly_activity

1. **repositories.py** (Line 182)
   - Arguments: (self, hours)
2. **selectors.py** (Line 187)
   - Arguments: (self, hours)

### get_hours_default

1. **models.py** (Line 54)
2. **serializers.py** (Line 45)

### get_ident

1. **throttling.py** (Line 80)
   - Arguments: (self, request)
2. **throttling.py** (Line 158)
   - Arguments: (self, request)
3. **throttling.py** (Line 171)
   - Arguments: (self, request)

### get_incident_statistics

1. **managers.py** (Line 226)
   - Arguments: (self, days)
2. **repositories.py** (Line 411)
   - Arguments: (self, days)
3. **services\IncidentService.py** (Line 463)
   - Arguments: (self)

### get_info

1. **endpoint.py** (Line 132)
   - Arguments: (self)
2. **plugins.py** (Line 46)
   - Arguments: (self)
3. **resources.py** (Line 183)
   - Arguments: (self)

### get_is_expired

1. **serializers.py** (Line 8758)
   - Arguments: (self, obj)
2. **serializers.py** (Line 11937)
   - Arguments: (self, obj)
3. **serializers.py** (Line 12055)
   - Arguments: (self, obj)

### get_is_suspicious

1. **serializers.py** (Line 4133)
   - Arguments: (self, obj)
2. **serializers.py** (Line 10557)
   - Arguments: (self, obj)

### get_last_run_ago

1. **serializers.py** (Line 9759)
   - Arguments: (self, obj)
2. **serializers.py** (Line 11139)
   - Arguments: (self, obj)

### get_latest_version

1. **models.py** (Line 6282)
   - Arguments: (cls, platform)
2. **integration_system\versioning.py** (Line 178)
   - Arguments: (self, integration_name)

### get_location

1. **dependencies.py** (Line 434)
   - Arguments: (self, ip_address)
2. **dependencies.py** (Line 760)
   - Arguments: (self, ip_address)

### get_many

1. **caching.py** (Line 135)
   - Arguments: (self, keys)
2. **utils\cache_manager.py** (Line 256)
   - Arguments: (keys)

### get_metadata_value

1. **abstracts.py** (Line 50)
   - Arguments: (self, key, default)
2. **model_mixins.py** (Line 95)
   - Arguments: (self, key, default)

### get_metrics

1. **abstracts.py** (Line 232)
   - Arguments: (self)
2. **plugins.py** (Line 132)
   - Arguments: (self)
3. **plugins.py** (Line 650)
   - Arguments: (self)
4. **plugins.py** (Line 688)
   - Arguments: (self)
5. **integration_system\integ_registry.py** (Line 408)
   - Arguments: (self)

### get_monitor

1. **monitoring.py** (Line 643)
   - Arguments: (self, name)
2. **integration_system\performance_monitor.py** (Line 428)
   - Arguments: (self, monitor_name)

### get_monthly_stats

1. **serializers.py** (Line 9873)
   - Arguments: (self, obj)
2. **serializers.py** (Line 11253)
   - Arguments: (self, obj)

### get_next_run_in

1. **serializers.py** (Line 9781)
   - Arguments: (self, obj)
2. **serializers.py** (Line 11161)
   - Arguments: (self, obj)

### get_object

1. **views.py** (Line 741)
   - Arguments: (self)
2. **views.py** (Line 8130)
   - Arguments: (self)
3. **views.py** (Line 8974)
   - Arguments: (self)

### get_paginated_response

1. **pagination.py** (Line 27)
   - Arguments: (self, data)
2. **pagination.py** (Line 122)
   - Arguments: (self, data)
3. **pagination.py** (Line 254)
   - Arguments: (self, items, next_cursor, has_next, request)
4. **pagination.py** (Line 288)
   - Arguments: (self, items, has_more, page, request)
5. **pagination.py** (Line 350)
   - Arguments: (self, items, has_next, page, total_count, search_query, request)
6. **pagination.py** (Line 428)
   - Arguments: (self, items, has_next, page, total_count, request)
7. **pagination.py** (Line 485)
   - Arguments: (self)
8. **pagination.py** (Line 552)
   - Arguments: (self, items, has_next, page, total_count, request)
9. **views.py** (Line 141)
   - Arguments: (self, data)

### get_pagination_metadata

1. **pagination.py** (Line 54)
   - Arguments: (self)
2. **pagination.py** (Line 145)
   - Arguments: (self)

### get_performance_metrics

1. **serializers.py** (Line 9890)
   - Arguments: (self, obj)
2. **serializers.py** (Line 11270)
   - Arguments: (self, obj)

### get_performance_report

1. **integration_system\message_queue.py** (Line 524)
   - Arguments: (self)
2. **integration_system\performance_monitor.py** (Line 270)
   - Arguments: (self)

### get_performance_score

1. **serializers.py** (Line 9725)
   - Arguments: (self, obj)
2. **serializers.py** (Line 11105)
   - Arguments: (self, obj)

### get_permissions

1. **views.py** (Line 604)
   - Arguments: (self)
2. **views.py** (Line 1730)
   - Arguments: (self)
3. **views.py** (Line 1913)
   - Arguments: (self)
4. **views.py** (Line 4074)
   - Arguments: (self)

### get_policy_statistics

1. **managers.py** (Line 703)
   - Arguments: (self)
2. **services\SecurityPolicyService.py** (Line 453)
   - Arguments: (self, tenant)

### get_priority_distribution

1. **managers.py** (Line 718)
   - Arguments: (self)
2. **selectors.py** (Line 430)
   - Arguments: (self)

### get_queryset

1. **abstracts.py** (Line 339)
   - Arguments: (self)
2. **admin.py** (Line 668)
   - Arguments: (self, request)
3. **managers.py** (Line 24)
   - Arguments: (self)
4. **managers.py** (Line 161)
   - Arguments: (self)
5. **managers.py** (Line 272)
   - Arguments: (self)
6. **managers.py** (Line 380)
   - Arguments: (self)
7. **managers.py** (Line 482)
   - Arguments: (self)
8. **managers.py** (Line 569)
   - Arguments: (self)
9. **managers.py** (Line 654)
   - Arguments: (self)
10. **managers.py** (Line 730)
   - Arguments: (self)
11. **managers.py** (Line 821)
   - Arguments: (self)
12. **models.py** (Line 612)
   - Arguments: (self)
13. **models.py** (Line 4715)
   - Arguments: (self, request)
14. **serializers.py** (Line 7757)
   - Arguments: (self)
15. **views.py** (Line 634)
   - Arguments: (self)
16. **views.py** (Line 1741)
   - Arguments: (self)
17. **views.py** (Line 1924)
   - Arguments: (self)
18. **views.py** (Line 4105)
   - Arguments: (self)
19. **views.py** (Line 5100)
   - Arguments: (self)
20. **views.py** (Line 5822)
   - Arguments: (self)
21. **views.py** (Line 6877)
   - Arguments: (self)
22. **views.py** (Line 7902)
   - Arguments: (self)
23. **views.py** (Line 8114)
   - Arguments: (self)
24. **views.py** (Line 8955)
   - Arguments: (self)
25. **views.py** (Line 9037)
   - Arguments: (self)
26. **views.py** (Line 9137)
   - Arguments: (self)
27. **views.py** (Line 9222)
   - Arguments: (self)
28. **views.py** (Line 9297)
   - Arguments: (self)
29. **views.py** (Line 9404)
   - Arguments: (self)
30. **views.py** (Line 9494)
   - Arguments: (self)
31. **views.py** (Line 10079)
   - Arguments: (self)
32. **views.py** (Line 10384)
   - Arguments: (self)
33. **views.py** (Line 10424)
   - Arguments: (self)
34. **views.py** (Line 10492)
   - Arguments: (self)
35. **views.py** (Line 10544)
   - Arguments: (self)
36. **views.py** (Line 10581)
   - Arguments: (self)
37. **views.py** (Line 10610)
   - Arguments: (self)
38. **viewset.py** (Line 54)
   - Arguments: (self)
39. **viewset.py** (Line 183)
   - Arguments: (self)
40. **viewset.py** (Line 405)
   - Arguments: (self)

### get_queue_status

1. **integration_system\event_bus.py** (Line 348)
   - Arguments: (self)
2. **integration_system\integ_handler.py** (Line 277)
   - Arguments: (self)

### get_rate_limit_status

1. **caching.py** (Line 382)
   - Arguments: (self, key, window)
2. **utils.py** (Line 449)
   - Arguments: (identifier)

### get_readonly_fields

1. **admin.py** (Line 676)
   - Arguments: (self, request, obj)
2. **models.py** (Line 4734)
   - Arguments: (self, request, obj)

### get_remaining_time

1. **exceptions.py** (Line 122)
   - Arguments: (self)
2. **serializers.py** (Line 5471)
   - Arguments: (self, obj)
3. **serializers.py** (Line 6109)
   - Arguments: (self, obj)

### get_report_types

1. **abstracts.py** (Line 204)
   - Arguments: (self)
2. **plugins.py** (Line 146)
   - Arguments: (self)
3. **plugins.py** (Line 732)
   - Arguments: (self)
4. **plugins.py** (Line 771)
   - Arguments: (self)

### get_response

1. **tests\test_middleware.py** (Line 70)
   - Arguments: (request)
2. **tests\test_middleware.py** (Line 98)
   - Arguments: (request)
3. **tests\test_middleware.py** (Line 120)
   - Arguments: (request)
4. **tests\test_middleware.py** (Line 143)
   - Arguments: (request)
5. **tests\test_middleware.py** (Line 161)
   - Arguments: (request)
6. **tests\test_middleware.py** (Line 176)
   - Arguments: (request)
7. **tests\test_middleware.py** (Line 214)
   - Arguments: (request)
8. **tests\test_middleware.py** (Line 241)
   - Arguments: (request)
9. **tests\test_middleware.py** (Line 257)
   - Arguments: (request)
10. **tests\test_middleware.py** (Line 447)
   - Arguments: (request)
11. **tests\test_middleware.py** (Line 476)
   - Arguments: (request)
12. **tests\test_middleware.py** (Line 502)
   - Arguments: (request)
13. **tests\test_middleware.py** (Line 522)
   - Arguments: (request)
14. **tests\test_middleware.py** (Line 568)
   - Arguments: (request)
15. **tests\test_middleware.py** (Line 589)
   - Arguments: (request)
16. **tests\test_middleware.py** (Line 623)
   - Arguments: (request)
17. **tests\test_middleware.py** (Line 651)
   - Arguments: (request)
18. **tests\test_middleware.py** (Line 675)
   - Arguments: (request)
19. **tests\test_middleware.py** (Line 742)
   - Arguments: (request)
20. **tests\test_middleware.py** (Line 760)
   - Arguments: (request)
21. **tests\test_middleware.py** (Line 198)
   - Arguments: (request)
22. **tests\test_middleware.py** (Line 280)
   - Arguments: (request)
23. **tests\test_middleware.py** (Line 304)
   - Arguments: (request)
24. **tests\test_middleware.py** (Line 333)
   - Arguments: (request)
25. **tests\test_middleware.py** (Line 355)
   - Arguments: (request)
26. **tests\test_middleware.py** (Line 382)
   - Arguments: (request)
27. **tests\test_middleware.py** (Line 405)
   - Arguments: (request)
28. **tests\test_middleware.py** (Line 427)
   - Arguments: (request)
29. **tests\test_middleware.py** (Line 547)
   - Arguments: (request)
30. **tests\test_middleware.py** (Line 705)
   - Arguments: (request)
31. **tests\test_middleware.py** (Line 800)
   - Arguments: (request)

### get_risk_assessment

1. **serializers.py** (Line 3328)
   - Arguments: (self, obj)
2. **serializers.py** (Line 10545)
   - Arguments: (self, obj)

### get_risk_distribution

1. **managers.py** (Line 524)
   - Arguments: (self)
2. **selectors.py** (Line 296)
   - Arguments: (self)

### get_risk_level

1. **context_processors.py** (Line 279)
   - Arguments: (risk_score)
2. **models.py** (Line 388)
   - Arguments: (self)
3. **serializers.py** (Line 4645)
   - Arguments: (self, obj)
4. **serializers.py** (Line 6842)
   - Arguments: (self, obj)
5. **serializers.py** (Line 9063)
   - Arguments: (self, obj)

### get_risk_level_display

1. **models.py** (Line 401)
   - Arguments: (self)
2. **serializers.py** (Line 4160)
   - Arguments: (self, obj)

### get_risk_score

1. **events.py** (Line 73)
   - Arguments: (self)
2. **events.py** (Line 116)
   - Arguments: (self)
3. **events.py** (Line 155)
   - Arguments: (self)
4. **events.py** (Line 184)
   - Arguments: (self)
5. **events.py** (Line 224)
   - Arguments: (self)
6. **serializers.py** (Line 10489)
   - Arguments: (self, obj)

### get_schema

1. **schemas.py** (Line 41)
   - Arguments: (self)
2. **schemas.py** (Line 126)
   - Arguments: (self)
3. **schemas.py** (Line 228)
   - Arguments: (self)
4. **schemas.py** (Line 320)
   - Arguments: (self)
5. **schemas.py** (Line 431)
   - Arguments: (self)
6. **schemas.py** (Line 497)
   - Arguments: (self)
7. **schemas.py** (Line 584)
   - Arguments: (self)
8. **schemas.py** (Line 688)
   - Arguments: (self, schema_type)

### get_security_flags

1. **models.py** (Line 413)
   - Arguments: (self)
2. **serializers.py** (Line 4188)
   - Arguments: (self, obj)

### get_security_metrics

1. **consumers.py** (Line 544)
   - Arguments: (self)
2. **context_processors.py** (Line 214)
   - Arguments: (request)

### get_security_stats

1. **admin.py** (Line 6966)
   - Arguments: (self, date_ranges)
2. **caching.py** (Line 288)
   - Arguments: (self, period, filters)

### get_security_summary

1. **serializers.py** (Line 8209)
   - Arguments: (self, obj)
2. **services\SecurityInsightService.py** (Line 375)
   - Arguments: (self, days)

### get_security_types_count

1. **repositories.py** (Line 166)
   - Arguments: (self)
2. **selectors.py** (Line 171)
   - Arguments: (self)

### get_serializer_class

1. **views.py** (Line 4090)
   - Arguments: (self)
2. **views.py** (Line 5075)
   - Arguments: (self)
3. **views.py** (Line 5809)
   - Arguments: (self)
4. **views.py** (Line 6864)
   - Arguments: (self)
5. **views.py** (Line 7894)
   - Arguments: (self)
6. **views.py** (Line 10378)
   - Arguments: (self)
7. **views.py** (Line 10418)
   - Arguments: (self)
8. **views.py** (Line 10486)
   - Arguments: (self)
9. **views.py** (Line 10575)
   - Arguments: (self)
10. **viewset.py** (Line 65)
   - Arguments: (self)
11. **viewset.py** (Line 413)
   - Arguments: (self)

### get_service_instance

1. **services\IncidentService.py** (Line 584)
   - Arguments: (cls)
2. **services\PasswordHistoryService.py** (Line 36)
   - Arguments: (cls)
3. **services\SecurityInsightService.py** (Line 37)
   - Arguments: (cls)
4. **services\SecurityPolicyService.py** (Line 36)
   - Arguments: (cls)
5. **services\ThreatIntelService.py** (Line 625)
   - Arguments: (cls)
6. **services\TrustedDeviceService.py** (Line 36)
   - Arguments: (cls)

### get_severity_breakdown

1. **models.py** (Line 8595)
   - Arguments: (self)
2. **serializers.py** (Line 12165)
   - Arguments: (self, obj)

### get_severity_display

1. **serializers.py** (Line 11933)
   - Arguments: (self, obj)
2. **serializers.py** (Line 11998)
   - Arguments: (self, obj)

### get_severity_distribution

1. **managers.py** (Line 106)
   - Arguments: (self, days)
2. **repositories.py** (Line 170)
   - Arguments: (self)
3. **selectors.py** (Line 179)
   - Arguments: (self)
4. **selectors.py** (Line 569)
   - Arguments: (self)

### get_signal_statistics

1. **signals_cap.py** (Line 182)
   - Arguments: (self)
2. **integration_system\integ_signals.py** (Line 268)
   - Arguments: (self)

### get_source_distribution

1. **managers.py** (Line 360)
   - Arguments: (self)
2. **selectors.py** (Line 561)
   - Arguments: (self)

### get_statistics

1. **hooks.py** (Line 84)
   - Arguments: (self)
2. **signals_kb.py** (Line 157)
   - Arguments: (self)
3. **integration_system\circuit_breaker.py** (Line 140)
   - Arguments: (self)
4. **integration_system\data_validator.py** (Line 394)
   - Arguments: (self)
5. **integration_system\event_bus.py** (Line 143)
   - Arguments: (self)
6. **integration_system\event_bus.py** (Line 328)
   - Arguments: (self)
7. **integration_system\fallback_logic.py** (Line 89)
   - Arguments: (self)
8. **integration_system\integ_audit_logs.py** (Line 315)
   - Arguments: (self)
9. **integration_system\sync_manager.py** (Line 502)
   - Arguments: (self)
10. **integration_system\transformer.py** (Line 113)
   - Arguments: (self)

### get_status

1. **abstracts.py** (Line 107)
   - Arguments: (self)
2. **dependencies.py** (Line 77)
   - Arguments: (self)
3. **dependencies.py** (Line 125)
   - Arguments: (self)
4. **dependencies.py** (Line 288)
   - Arguments: (self)
5. **dependencies.py** (Line 403)
   - Arguments: (self)
6. **dependencies.py** (Line 516)
   - Arguments: (self)
7. **monitoring.py** (Line 151)
   - Arguments: (self)
8. **serializers.py** (Line 8881)
   - Arguments: (self, obj)
9. **integration_system\auth_bridge.py** (Line 522)
   - Arguments: (self)
10. **integration_system\bridge.py** (Line 251)
   - Arguments: (self)
11. **integration_system\health_check.py** (Line 126)
   - Arguments: (self)
12. **integration_system\integ_adapter.py** (Line 173)
   - Arguments: (self)
13. **integration_system\integ_audit_logs.py** (Line 493)
   - Arguments: (self)
14. **integration_system\message_queue.py** (Line 276)
   - Arguments: (self)
15. **integration_system\versioning.py** (Line 222)
   - Arguments: (self)

### get_strategy

1. **integration_system\fallback_logic.py** (Line 391)
   - Arguments: (self, strategy_name)
2. **integration_system\sync_manager.py** (Line 283)
   - Arguments: (self, strategy_name)

### get_success_rate

1. **serializers.py** (Line 9933)
   - Arguments: (self, obj)
2. **serializers.py** (Line 11313)
   - Arguments: (self, obj)

### get_system_health

1. **caching.py** (Line 302)
   - Arguments: (self)
2. **context_processors.py** (Line 370)

### get_threat_statistics

1. **repositories.py** (Line 497)
   - Arguments: (self)
2. **services\ThreatIntelService.py** (Line 552)
   - Arguments: (self)

### get_threat_types

1. **abstracts.py** (Line 174)
   - Arguments: (self)
2. **plugins.py** (Line 99)
   - Arguments: (self)
3. **plugins.py** (Line 475)
   - Arguments: (self)
4. **plugins.py** (Line 523)
   - Arguments: (self)

### get_today_stats

1. **serializers.py** (Line 9829)
   - Arguments: (self, obj)
2. **serializers.py** (Line 11209)
   - Arguments: (self, obj)

### get_top_ip_addresses

1. **repositories.py** (Line 174)
   - Arguments: (self, limit)
2. **selectors.py** (Line 154)
   - Arguments: (self, limit)

### get_top_users

1. **managers.py** (Line 126)
   - Arguments: (self, days, limit)
2. **repositories.py** (Line 178)
   - Arguments: (self, limit)
3. **selectors.py** (Line 162)
   - Arguments: (self, limit)

### get_type_distribution

1. **managers.py** (Line 352)
   - Arguments: (self)
2. **managers.py** (Line 459)
   - Arguments: (self)
3. **managers.py** (Line 636)
   - Arguments: (self)
4. **managers.py** (Line 712)
   - Arguments: (self)
5. **selectors.py** (Line 438)
   - Arguments: (self)
6. **selectors.py** (Line 553)
   - Arguments: (self)

### get_uptime_percentage

1. **serializers.py** (Line 9709)
   - Arguments: (self, obj)
2. **serializers.py** (Line 11089)
   - Arguments: (self, obj)

### get_user_device_count

1. **managers.py** (Line 465)
   - Arguments: (self, user)
2. **selectors.py** (Line 324)
   - Arguments: (self, user)

### get_user_devices

1. **caching.py** (Line 249)
   - Arguments: (self, user_id)
2. **context_processors.py** (Line 291)
   - Arguments: (user)
3. **utils\cache_manager.py** (Line 708)
   - Arguments: (self)

### get_user_info

1. **serializers.py** (Line 3307)
   - Arguments: (self, obj)
2. **serializers.py** (Line 4879)
   - Arguments: (self, obj)
3. **serializers.py** (Line 5439)
   - Arguments: (self, obj)
4. **serializers.py** (Line 6826)
   - Arguments: (self, obj)
5. **serializers.py** (Line 8182)
   - Arguments: (self, obj)
6. **serializers.py** (Line 11970)
   - Arguments: (self, obj)
7. **serializers.py** (Line 12041)
   - Arguments: (self, obj)
8. **serializers.py** (Line 12080)
   - Arguments: (self, obj)

### get_user_sanctions

1. **caching.py** (Line 259)
   - Arguments: (self, user_id)
2. **sanctions.py** (Line 393)
   - Arguments: (self, user, active_only)

### get_user_summary

1. **serializers.py** (Line 3504)
   - Arguments: (self, obj)
2. **serializers.py** (Line 4684)
   - Arguments: (self, obj)
3. **serializers.py** (Line 5100)
   - Arguments: (self, obj)
4. **serializers.py** (Line 5654)
   - Arguments: (self, obj)
5. **serializers.py** (Line 7098)
   - Arguments: (self, obj)

### get_username

1. **serializers.py** (Line 11839)
   - Arguments: (self, obj)
2. **serializers.py** (Line 11898)
   - Arguments: (self, obj)

### get_weekly_stats

1. **serializers.py** (Line 9852)
   - Arguments: (self, obj)
2. **serializers.py** (Line 11232)
   - Arguments: (self, obj)

### handle

1. **abstracts.py** (Line 418)
   - Arguments: (self, event)
2. **integration_system\data_bridge.py** (Line 74)
   - Arguments: (self, event_data)
3. **integration_system\integ_handler.py** (Line 317)
   - Arguments: (self, event_data)
4. **integration_system\webhooks_integration.py** (Line 79)
   - Arguments: (self, event_data)
5. **management\commands\block_suspicious_ips.py** (Line 99)
   - Arguments: (self)
6. **management\commands\export_security_report.py** (Line 106)
   - Arguments: (self)
7. **management\commands\run_security_scan.py** (Line 81)
   - Arguments: (self)
8. **management\commands\seed_security_rules.py** (Line 73)
   - Arguments: (self)
9. **management\commands\unlock_user_accounts.py** (Line 108)
   - Arguments: (self)

### handle_exception

1. **exceptions.py** (Line 526)
   - Arguments: (exception)
2. **serializers.py** (Line 479)
   - Arguments: (self, exc)
3. **views.py** (Line 4008)
   - Arguments: (exception, context)
4. **views.py** (Line 4989)
   - Arguments: (exception, context)
5. **views.py** (Line 5091)
   - Arguments: (self, exc)
6. **views.py** (Line 5712)
   - Arguments: (exception, context)
7. **views.py** (Line 6779)
   - Arguments: (exception, context)
8. **integration_system\integ_exceptions.py** (Line 408)
   - Arguments: (self, exception, context)

### handle_gracefully

1. **decorators.py** (Line 29)
   - Arguments: (default_response)
2. **decorators.py** (Line 530)
   - Arguments: (default_return, log_error)
3. **decorators.py** (Line 1304)
   - Arguments: (default_response, log_errors, retry_count)
4. **serializers.py** (Line 91)
   - Arguments: (default_response)
5. **views.py** (Line 372)
   - Arguments: (func)
6. **utils\cache_manager.py** (Line 311)
   - Arguments: (default_return, log_errors, suppress_errors, retry_count, retry_delay)

### handle_gracefully_method

1. **decorators.py** (Line 1383)
   - Arguments: (default_response, log_errors, retry_count)
2. **utils\cache_manager.py** (Line 417)
   - Arguments: (default_return, log_errors, suppress_errors, include_context)

### has_add_permission

1. **admin.py** (Line 3981)
   - Arguments: (self, request)
2. **admin.py** (Line 3992)
   - Arguments: (self, request)
3. **admin.py** (Line 4077)
   - Arguments: (self, request)
4. **admin.py** (Line 4096)
   - Arguments: (self, request)
5. **admin.py** (Line 4115)
   - Arguments: (self, request)
6. **admin.py** (Line 4169)
   - Arguments: (self, request)
7. **admin.py** (Line 4202)
   - Arguments: (self, request)

### has_object_permission

1. **mixins.py** (Line 512)
   - Arguments: (self, request, view, obj)
2. **permissions.py** (Line 163)
   - Arguments: (self, request, view, obj)
3. **permissions.py** (Line 185)
   - Arguments: (self, request, view, obj)
4. **permissions_backup.py** (Line 160)
   - Arguments: (self, request, view, obj)
5. **views.py** (Line 559)
   - Arguments: (self, request, view, obj)
6. **views.py** (Line 8097)
   - Arguments: (self, request, view, obj)

### has_permission

1. **mixins.py** (Line 502)
   - Arguments: (self, request, view)
2. **permissions.py** (Line 53)
   - Arguments: (self, request, view)
3. **permissions.py** (Line 69)
   - Arguments: (self, request, view)
4. **permissions.py** (Line 85)
   - Arguments: (self, request, view)
5. **permissions.py** (Line 131)
   - Arguments: (self, request, view)
6. **permissions.py** (Line 212)
   - Arguments: (self, request, view)
7. **permissions.py** (Line 250)
   - Arguments: (self, request, view)
8. **permissions.py** (Line 270)
   - Arguments: (self, request, view)
9. **permissions.py** (Line 295)
   - Arguments: (self, request, view)
10. **permissions.py** (Line 329)
   - Arguments: (self, request, view)
11. **permissions.py** (Line 351)
   - Arguments: (self, request, view)
12. **permissions.py** (Line 368)
   - Arguments: (self, request, view)
13. **permissions.py** (Line 389)
   - Arguments: (self, request, view)
14. **permissions_backup.py** (Line 53)
   - Arguments: (self, request, view)
15. **permissions_backup.py** (Line 68)
   - Arguments: (self, request, view)
16. **permissions_backup.py** (Line 83)
   - Arguments: (self, request, view)
17. **permissions_backup.py** (Line 128)
   - Arguments: (self, request, view)
18. **permissions_backup.py** (Line 190)
   - Arguments: (self, request, view)
19. **permissions_backup.py** (Line 216)
   - Arguments: (self, request, view)
20. **permissions_backup.py** (Line 245)
   - Arguments: (self, request, view)
21. **permissions_backup.py** (Line 277)
   - Arguments: (self, request, view)
22. **permissions_backup.py** (Line 319)
   - Arguments: (self, request, view)
23. **permissions_backup.py** (Line 358)
   - Arguments: (self, request, view)
24. **permissions_backup.py** (Line 397)
   - Arguments: (self, request, view)
25. **permissions_backup.py** (Line 434)
   - Arguments: (self, request, view)
26. **permissions_backup.py** (Line 471)
   - Arguments: (self, request, view)
27. **permissions_backup.py** (Line 506)
   - Arguments: (self, request, view)
28. **permissions_backup.py** (Line 538)
   - Arguments: (self, request, view)
29. **permissions_backup.py** (Line 697)
   - Arguments: (self, request, view)
30. **views.py** (Line 170)
   - Arguments: (self, request, view)
31. **views.py** (Line 181)
   - Arguments: (self, request, view)
32. **views.py** (Line 192)
   - Arguments: (self, request, view)
33. **views.py** (Line 201)
   - Arguments: (self, request, view)
34. **views.py** (Line 246)
   - Arguments: (self, request, view)
35. **views.py** (Line 270)
   - Arguments: (self, request, view)
36. **views.py** (Line 519)
   - Arguments: (self, request, view)
37. **views.py** (Line 540)
   - Arguments: (self, request, view)
38. **views.py** (Line 4054)
   - Arguments: (self, request, view)
39. **views.py** (Line 5054)
   - Arguments: (self, request, view)
40. **views.py** (Line 5788)
   - Arguments: (self, request, view)
41. **views.py** (Line 6843)
   - Arguments: (self, request, view)
42. **views.py** (Line 7880)
   - Arguments: (self, request, view)
43. **views.py** (Line 8094)
   - Arguments: (self, request, view)

### hash_data

1. **plugins.py** (Line 118)
   - Arguments: (self, data)
2. **plugins.py** (Line 568)
   - Arguments: (self, data)
3. **plugins.py** (Line 614)
   - Arguments: (self, data)

### hash_password

1. **encryption.py** (Line 581)
   - Arguments: (self, password, salt)
2. **utils\security_helpers.py** (Line 206)
   - Arguments: (password, algorithm)

### health_check

1. **endpoint.py** (Line 285)
   - Arguments: (request)
2. **resources.py** (Line 138)
   - Arguments: (self)

### high_confidence

1. **managers.py** (Line 314)
   - Arguments: (self, min_confidence)
2. **querysets.py** (Line 485)
   - Arguments: (self, threshold)

### high_priority

1. **managers.py** (Line 686)
   - Arguments: (self, min_priority)
2. **querysets.py** (Line 370)
   - Arguments: (self)

### high_risk

1. **managers.py** (Line 64)
   - Arguments: (self)
2. **managers.py** (Line 490)
   - Arguments: (self, min_score)
3. **querysets.py** (Line 147)
   - Arguments: (self, threshold)

### high_risk_devices

1. **models.py** (Line 620)
   - Arguments: (self)
2. **querysets.py** (Line 255)
   - Arguments: (self, threshold)

### inactive

1. **managers.py** (Line 431)
   - Arguments: (self, days)
2. **managers.py** (Line 662)
   - Arguments: (self)
3. **querysets.py** (Line 30)
   - Arguments: (self)

### initialize

1. **abstracts.py** (Line 93)
   - Arguments: (self, config)
2. **plugins.py** (Line 32)
   - Arguments: (self, config)
3. **plugins.py** (Line 362)
   - Arguments: (self, config)
4. **plugins.py** (Line 403)
   - Arguments: (self, config)
5. **plugins.py** (Line 440)
   - Arguments: (self, config)
6. **plugins.py** (Line 486)
   - Arguments: (self, config)
7. **plugins.py** (Line 534)
   - Arguments: (self, config)
8. **plugins.py** (Line 580)
   - Arguments: (self, config)
9. **plugins.py** (Line 626)
   - Arguments: (self, config)
10. **plugins.py** (Line 661)
   - Arguments: (self, config)
11. **plugins.py** (Line 699)
   - Arguments: (self, config)
12. **plugins.py** (Line 743)
   - Arguments: (self, config)
13. **resources.py** (Line 117)
   - Arguments: (self)
14. **integration_system\data_bridge.py** (Line 55)
   - Arguments: (self)
15. **integration_system\integ_handler.py** (Line 306)
   - Arguments: (self)
16. **integration_system\webhooks_integration.py** (Line 61)
   - Arguments: (self)

### ip_display

1. **admin.py** (Line 1764)
   - Arguments: (self, obj)
2. **admin.py** (Line 4032)
   - Arguments: (self, obj)

### is_active

1. **models.py** (Line 3432)
   - Arguments: (self)
2. **sanctions.py** (Line 132)
   - Arguments: (self)

### is_currently_active

1. **models.py** (Line 3252)
   - Arguments: (self)
2. **models.py** (Line 5091)
   - Arguments: (self)
3. **models.py** (Line 6207)
   - Arguments: (self)

### is_enabled

1. **dependencies.py** (Line 81)
   - Arguments: (self)
2. **feature_flags.py** (Line 281)
   - Arguments: (self, key, user, ip_address)

### is_expired

1. **encryption.py** (Line 49)
   - Arguments: (self)
2. **models.py** (Line 1417)
   - Arguments: (self)
3. **models.py** (Line 2032)
   - Arguments: (self)
4. **models.py** (Line 2732)
   - Arguments: (self)
5. **models.py** (Line 8193)
   - Arguments: (self)
6. **models.py** (Line 8382)
   - Arguments: (self)
7. **notifications_push.py** (Line 124)
   - Arguments: (self)
8. **sanctions.py** (Line 149)
   - Arguments: (self)
9. **integration_system\event_bus.py** (Line 64)
   - Arguments: (self)
10. **integration_system\message_queue.py** (Line 68)
   - Arguments: (self)

### is_high_risk

1. **exceptions.py** (Line 240)
   - Arguments: (self)
2. **model_mixins.py** (Line 171)
   - Arguments: (self)

### is_private_ip

1. **common_imports.py** (Line 226)
   - Arguments: (ip)
2. **utils.py** (Line 94)
   - Arguments: (ip)
3. **validators.py** (Line 574)
   - Arguments: (ip_address)

### is_rate_limited

1. **utils.py** (Line 432)
   - Arguments: (identifier, limit, window)
2. **utils\security_helpers.py** (Line 505)
   - Arguments: (identifier, action, limit, window)

### is_security_admin

1. **consumers.py** (Line 293)
   - Arguments: (self)
2. **consumers.py** (Line 616)
   - Arguments: (self)

### is_valid

1. **models.py** (Line 2987)
   - Arguments: (self)
2. **model_mixins.py** (Line 282)
   - Arguments: (self)
3. **utils\__init__.py** (Line 24)
   - Arguments: (value, expected_type)

### list

1. **abstracts.py** (Line 335)
   - Arguments: (self, filters)
2. **views.py** (Line 778)
   - Arguments: (self, request)
3. **views.py** (Line 4181)
   - Arguments: (self, request)
4. **views.py** (Line 5175)
   - Arguments: (self, request)
5. **views.py** (Line 5925)
   - Arguments: (self, request)
6. **views.py** (Line 6973)
   - Arguments: (self, request)
7. **views.py** (Line 7931)
   - Arguments: (self, request)
8. **views.py** (Line 8159)
   - Arguments: (self, request)
9. **views.py** (Line 8984)
   - Arguments: (self, request)
10. **viewset.py** (Line 83)
   - Arguments: (self, request)

### log_action

1. **models.py** (Line 1323)
   - Arguments: (cls, user, action_type, model_name, object_id)
2. **models.py** (Line 4325)
   - Arguments: (cls, user, action_type, ip_address, device_info, metadata)

### log_error

1. **decorators.py** (Line 626)
   - Arguments: (func_name, error)
2. **serializers.py** (Line 3813)
   - Arguments: (self, operation, error, context)

### log_event

1. **integration_system\integ_audit_logs.py** (Line 41)
   - Arguments: (self, event_type, message, severity, user, integration_name, metadata)
2. **integration_system\integ_audit_logs.py** (Line 408)
   - Arguments: (self, logger_name, event_type, message, severity)

### log_execution

1. **interactors.py** (Line 44)
   - Arguments: (self, interactor_name, result, error)
2. **use_cases.py** (Line 40)
   - Arguments: (self, use_case_name, result, error)

### log_security_event

1. **consumers.py** (Line 306)
   - Arguments: (self, event_type, metadata)
2. **serializers.py** (Line 3194)
   - Arguments: (sender, instance, created)
3. **services.py** (Line 151)
   - Arguments: (user, event_type, severity, metadata, ip_address, user_agent, device_info)
4. **utils.py** (Line 258)
   - Arguments: (event_type, details)
5. **views.py** (Line 3518)
   - Arguments: (request, event_type, severity, description, user, metadata)

### low_risk

1. **managers.py** (Line 498)
   - Arguments: (self, max_score)
2. **querysets.py** (Line 151)
   - Arguments: (self, threshold)

### mark_as_deprecated

1. **admin.py** (Line 2695)
   - Arguments: (self, request, queryset)
2. **models.py** (Line 6265)
   - Arguments: (self, reason)

### mark_as_suspicious

1. **admin.py** (Line 587)
   - Arguments: (self, request, queryset)
2. **models.py** (Line 3729)
   - Arguments: (self, reason)

### method_audit_action

1. **decorators.py** (Line 486)
   - Arguments: (action_type, log_level)
2. **decorators.py** (Line 772)
   - Arguments: (action_type, log_errors, fallback_to_super)
3. **views.py** (Line 331)
   - Arguments: (action_type)
4. **utils\device.py** (Line 748)
   - Arguments: (action_name)

### monitor

1. **plugins.py** (Line 127)
   - Arguments: (self, target)
2. **plugins.py** (Line 639)
   - Arguments: (self, target)
3. **plugins.py** (Line 674)
   - Arguments: (self, target)

### on_threat_detected

1. **notifications_push.py** (Line 698)
   - Arguments: (self, threat_data)
2. **webhooks.py** (Line 481)
   - Arguments: (self, threat_type, threat_data)

### order_by

1. **admin.py** (Line 6661)
   - Arguments: (self)
2. **repositories.py** (Line 122)
   - Arguments: (self)

### overview

1. **views.py** (Line 2032)
   - Arguments: (self, request)
2. **views.py** (Line 8458)
   - Arguments: (self, request)

### paginate_queryset

1. **pagination.py** (Line 63)
   - Arguments: (self, queryset)
2. **pagination.py** (Line 164)
   - Arguments: (self, queryset, request)
3. **pagination.py** (Line 272)
   - Arguments: (self, queryset, request)
4. **pagination.py** (Line 306)
   - Arguments: (self, queryset, request)
5. **pagination.py** (Line 371)
   - Arguments: (self, queryset, request)
6. **pagination.py** (Line 455)
   - Arguments: (self, queryset, request)
7. **pagination.py** (Line 515)
   - Arguments: (self, queryset, request)

### password

1. **factories.py** (Line 60)
   - Arguments: (obj, create, extracted)
2. **factories_backup.py** (Line 40)
   - Arguments: (obj, create, extracted)

### perform_create

1. **views.py** (Line 8144)
   - Arguments: (self, serializer)
2. **views.py** (Line 9237)
   - Arguments: (self, serializer)
3. **viewset.py** (Line 75)
   - Arguments: (self, serializer)

### permanent

1. **managers.py** (Line 284)
   - Arguments: (self)
2. **managers.py** (Line 583)
   - Arguments: (self)
3. **querysets.py** (Line 561)
   - Arguments: (self)

### post

1. **attachment_upload_view.py** (Line 47)
   - Arguments: (self, request)
2. **attachment_upload_view.py** (Line 312)
   - Arguments: (self, request)
3. **endpoint.py** (Line 395)
   - Arguments: (self, request)
4. **serializers.py** (Line 571)
   - Arguments: (self, request)
5. **serializers.py** (Line 839)
   - Arguments: (self, request)
6. **serializers.py** (Line 1470)
   - Arguments: (self, request)
7. **serializers.py** (Line 1612)
   - Arguments: (self, request)
8. **serializers.py** (Line 1792)
   - Arguments: (self, request)
9. **serializers.py** (Line 2062)
   - Arguments: (self, request)
10. **serializers.py** (Line 2160)
   - Arguments: (self, request)
11. **serializers.py** (Line 2261)
   - Arguments: (self, request)
12. **serializers.py** (Line 2346)
   - Arguments: (self, request)
13. **serializers.py** (Line 2459)
   - Arguments: (self, request)
14. **views.py** (Line 5529)
   - Arguments: (self, request)
15. **views.py** (Line 5624)
   - Arguments: (self, request)
16. **views.py** (Line 6357)
   - Arguments: (self, request)
17. **views.py** (Line 7484)
   - Arguments: (self, request)
18. **views.py** (Line 8510)
   - Arguments: (self, request)
19. **views.py** (Line 8884)
   - Arguments: (self, request)
20. **views.py** (Line 9724)
   - Arguments: (self, request)
21. **integration_system\webhooks_integration.py** (Line 394)
   - Arguments: (self, request, webhook_name)

### process

1. **abstracts.py** (Line 271)
   - Arguments: (self, data)
2. **signals_cap.py** (Line 270)
   - Arguments: (self, signal_record)
3. **signals_cap.py** (Line 293)
   - Arguments: (self, signal_record)
4. **signals_cap.py** (Line 366)
   - Arguments: (self, signal_record)
5. **signals_cap.py** (Line 431)
   - Arguments: (self, signal_record)

### progress_display

1. **admin.py** (Line 5390)
   - Arguments: (self, obj)
2. **admin.py** (Line 5666)
   - Arguments: (self, obj)

### quick_actions

1. **admin.py** (Line 348)
   - Arguments: (self, obj)
2. **admin.py** (Line 1411)
   - Arguments: (self, obj)
3. **admin.py** (Line 2902)
   - Arguments: (self, obj)

### rate_limit

1. **common_imports.py** (Line 264)
   - Arguments: (limit, period)
2. **decorators.py** (Line 124)
   - Arguments: (limit_type, requests_per_minute, cache_key_prefix)
3. **decorators.py** (Line 396)
   - Arguments: (limit_type, requests_per_minute, requests_per_hour)
4. **decorators.py** (Line 900)
   - Arguments: (max_requests, time_window, identifier_func)
5. **serializers.py** (Line 184)
   - Arguments: (limit_type, requests_per_minute, cache_key_prefix)
6. **views.py** (Line 451)
   - Arguments: (key_func, limit, timeout)

### reason_badge

1. **admin.py** (Line 1321)
   - Arguments: (self, obj)
2. **admin.py** (Line 2813)
   - Arguments: (self, obj)

### recalculate

1. **views.py** (Line 1948)
   - Arguments: (self, request, pk)
2. **views.py** (Line 7002)
   - Arguments: (self, request, pk)

### recent

1. **managers.py** (Line 51)
   - Arguments: (self, hours)
2. **managers.py** (Line 207)
   - Arguments: (self, days)
3. **managers.py** (Line 318)
   - Arguments: (self, days)
4. **managers.py** (Line 426)
   - Arguments: (self, days)
5. **managers.py** (Line 506)
   - Arguments: (self, days)
6. **managers.py** (Line 603)
   - Arguments: (self, days)
7. **managers.py** (Line 690)
   - Arguments: (self, days)
8. **managers.py** (Line 745)
   - Arguments: (self, days)
9. **managers.py** (Line 829)
   - Arguments: (self, days)
10. **querysets.py** (Line 36)
   - Arguments: (self, days)

### register

1. **endpoint.py** (Line 157)
   - Arguments: (self, endpoint)
2. **registry.py** (Line 82)
   - Arguments: (self, registration)
3. **resources.py** (Line 466)
   - Arguments: (self, resource)

### register_adapter

1. **integration_system\integ_adapter.py** (Line 504)
   - Arguments: (self, adapter)
2. **integration_system\integ_registry.py** (Line 75)
   - Arguments: (self, adapter_name, adapter_class, configuration)

### register_capability

1. **tasks_cap.py** (Line 548)
   - Arguments: (self, capability)
2. **viewset_cap.py** (Line 651)
   - Arguments: (self, capability)

### register_filter

1. **events.py** (Line 351)
   - Arguments: (self, pattern, filter_func)
2. **signals_cap.py** (Line 146)
   - Arguments: (self, signal_name, filter_func)

### register_handler

1. **events.py** (Line 334)
   - Arguments: (self, pattern, handler)
2. **signals_cap.py** (Line 154)
   - Arguments: (self, signal_name, handler)
3. **integration_system\integ_exceptions.py** (Line 397)
   - Arguments: (self, exception_type, handler)

### register_integration

1. **integration_system\integ_handler.py** (Line 37)
   - Arguments: (self, integration_name, integration_class)
2. **integration_system\integ_registry.py** (Line 39)
   - Arguments: (self, integration_name, integration_class, dependencies, configuration)

### remove_ip_from_whitelist

1. **models.py** (Line 7888)
   - Arguments: (self, ip_address)
2. **views.py** (Line 8342)
   - Arguments: (self, request, pk)

### remove_monitor

1. **monitoring.py** (Line 599)
   - Arguments: (self, name)
2. **integration_system\performance_monitor.py** (Line 420)
   - Arguments: (self, monitor_name)

### remove_rule

1. **abstracts.py** (Line 523)
   - Arguments: (self, rule_name)
2. **integration_system\data_validator.py** (Line 261)
   - Arguments: (self, rule_name)

### require_enhanced_permission

1. **permissions.py** (Line 420)
   - Arguments: (required_permissions, require_all)
2. **permissions_backup.py** (Line 636)
   - Arguments: (permission_name)

### require_permission

1. **permissions.py** (Line 406)
   - Arguments: (permission)
2. **permissions_backup.py** (Line 614)
   - Arguments: (permission_class)

### reset_stats

1. **admin.py** (Line 6122)
   - Arguments: (self, request, queryset)
2. **caching.py** (Line 213)
   - Arguments: (self)

### resolve

1. **views.py** (Line 1765)
   - Arguments: (self, request, pk)
2. **views.py** (Line 10453)
   - Arguments: (self, request, pk)

### resolve_conflict

1. **integration_system\sync_manager.py** (Line 32)
   - Arguments: (self, source_data, target_data, conflict_info)
2. **integration_system\sync_manager.py** (Line 57)
   - Arguments: (self, source_data, target_data, conflict_info)
3. **integration_system\sync_manager.py** (Line 75)
   - Arguments: (self, source_data, target_data, conflict_info)
4. **integration_system\sync_manager.py** (Line 93)
   - Arguments: (self, source_data, target_data, conflict_info)
5. **integration_system\sync_manager.py** (Line 161)
   - Arguments: (self, source_data, target_data, conflict_info)
6. **integration_system\sync_manager.py** (Line 220)
   - Arguments: (self, source_data, target_data, conflict_info)

### retry_on_failure

1. **tests.py** (Line 275)
   - Arguments: (max_retries, delay)
2. **utils\cache_manager.py** (Line 560)
   - Arguments: (func, max_retries, delay, backoff, exceptions, default, log_retries)

### revoke_trust

1. **views.py** (Line 10513)
   - Arguments: (self, request, pk)
2. **services\TrustedDeviceService.py** (Line 150)
   - Arguments: (self, device_id, reason)

### risk_meter

1. **admin.py** (Line 229)
   - Arguments: (self, obj)
2. **admin.py** (Line 3615)
   - Arguments: (self, obj)

### risk_score_display

1. **admin.py** (Line 370)
   - Arguments: (self, obj)
2. **admin.py** (Line 914)
   - Arguments: (self, obj)

### safe_action

1. **admin.py** (Line 85)
   - Arguments: (message_on_error)
2. **views.py** (Line 421)
   - Arguments: (error_message, error_code)

### safe_execute

1. **utils\cache_manager.py** (Line 499)
   - Arguments: (func)
2. **utils\__init__.py** (Line 29)
   - Arguments: (func)

### safe_get_user

1. **serializers.py** (Line 5314)
   - Arguments: (user_id)
2. **serializers.py** (Line 5923)
   - Arguments: (user_id)
3. **serializers.py** (Line 6680)
   - Arguments: (user_id)

### safe_get_value

1. **serializers.py** (Line 3603)
   - Arguments: (obj, field_name, default)
2. **serializers.py** (Line 3698)
   - Arguments: (self, obj, attr, default)

### safe_response

1. **views.py** (Line 3996)
   - Arguments: (data, status_code)
2. **views.py** (Line 4977)
   - Arguments: (data, status_code)
3. **views.py** (Line 5700)
   - Arguments: (data, status_code)
4. **views.py** (Line 6767)
   - Arguments: (data, status_code)

### sanitize_input

1. **serializers.py** (Line 3151)
   - Arguments: (data)
2. **utils.py** (Line 189)
   - Arguments: (input_string)

### save

1. **forms.py** (Line 261)
   - Arguments: (self)
2. **hash_chain.py** (Line 280)
   - Arguments: (self)
3. **mixins.py** (Line 30)
   - Arguments: (self)
4. **models.py** (Line 235)
   - Arguments: (self)
5. **models.py** (Line 781)
   - Arguments: (self)
6. **models.py** (Line 3230)
   - Arguments: (self)
7. **models.py** (Line 3644)
   - Arguments: (self)
8. **models.py** (Line 5049)
   - Arguments: (self)
9. **models.py** (Line 5676)
   - Arguments: (self)
10. **models.py** (Line 6179)
   - Arguments: (self)
11. **models.py** (Line 6658)
   - Arguments: (self)
12. **models.py** (Line 7592)
   - Arguments: (self)
13. **model_mixins.py** (Line 22)
   - Arguments: (self)

### save_model

1. **admin.py** (Line 685)
   - Arguments: (self, request, obj, form, change)
2. **models.py** (Line 4750)
   - Arguments: (self, request, obj, form, change)

### scan_file

1. **dependencies.py** (Line 322)
   - Arguments: (self, file_content, filename)
2. **dependencies.py** (Line 738)
   - Arguments: (self, file_content, filename)

### search

1. **querysets.py** (Line 81)
   - Arguments: (self, query, fields)
2. **search.py** (Line 163)
   - Arguments: (self, query, page, page_size, sort_by, sort_order)

### security_analysis

1. **admin.py** (Line 439)
   - Arguments: (self, obj)
2. **admin.py** (Line 3417)
   - Arguments: (self, obj)

### security_status

1. **admin.py** (Line 199)
   - Arguments: (self, obj)
2. **serializers.py** (Line 2929)
   - Arguments: (request)

### send_notification

1. **notifications_push.py** (Line 219)
   - Arguments: (self, user, title, message, notification_type, priority, data, platform, device_token)
2. **notifications_push.py** (Line 469)
   - Arguments: (self, notification, device_token)
3. **notifications_push.py** (Line 483)
   - Arguments: (self, notification, device_token)
4. **notifications_push.py** (Line 528)
   - Arguments: (self, notification, device_token)
5. **notifications_push.py** (Line 563)
   - Arguments: (self, notification, device_token)
6. **notifications_push.py** (Line 580)
   - Arguments: (self, notification, device_token)
7. **notifications_push.py** (Line 610)
   - Arguments: (self, notification, device_token)

### send_security_alert

1. **dependencies.py** (Line 539)
   - Arguments: (self, to_email, subject, message, priority)
2. **dependencies.py** (Line 780)
   - Arguments: (self, to_email, subject, message, priority)
3. **notifications_push.py** (Line 265)
   - Arguments: (self, user, alert_data)
4. **utils\device.py** (Line 181)
   - Arguments: (user, security_type, description, metadata)

### set

1. **abstracts.py** (Line 574)
   - Arguments: (self, key, value, ttl)
2. **caching.py** (Line 108)
   - Arguments: (self, key, value, ttl)
3. **utils\cache_manager.py** (Line 133)
   - Arguments: (key, value, timeout)

### setUp

1. **tests.py** (Line 60)
   - Arguments: (self)
2. **tests.py** (Line 297)
   - Arguments: (self)
3. **tests.py** (Line 1428)
   - Arguments: (self)
4. **tests.py** (Line 1642)
   - Arguments: (self)
5. **tests.py** (Line 2029)
   - Arguments: (self)
6. **tests.py** (Line 2198)
   - Arguments: (self)
7. **test_models.py** (Line 27)
   - Arguments: (self)
8. **test_models.py** (Line 118)
   - Arguments: (self)
9. **test_models.py** (Line 177)
   - Arguments: (self)
10. **test_models.py** (Line 292)
   - Arguments: (self)
11. **test_models.py** (Line 370)
   - Arguments: (self)
12. **test_models.py** (Line 567)
   - Arguments: (self)
13. **test_models.py** (Line 616)
   - Arguments: (self)
14. **test_models.py** (Line 671)
   - Arguments: (self)
15. **test_models.py** (Line 768)
   - Arguments: (self)
16. **test_serializers.py** (Line 36)
   - Arguments: (self)
17. **test_serializers.py** (Line 133)
   - Arguments: (self)
18. **test_serializers.py** (Line 213)
   - Arguments: (self)
19. **test_serializers.py** (Line 346)
   - Arguments: (self)
20. **test_serializers.py** (Line 471)
   - Arguments: (self)
21. **test_serializers.py** (Line 551)
   - Arguments: (self)
22. **test_serializers.py** (Line 598)
   - Arguments: (self)
23. **test_serializers.py** (Line 663)
   - Arguments: (self)
24. **test_serializers.py** (Line 779)
   - Arguments: (self)
25. **test_views.py** (Line 33)
   - Arguments: (self)
26. **test_views.py** (Line 67)
   - Arguments: (self)
27. **test_views.py** (Line 244)
   - Arguments: (self)
28. **test_views.py** (Line 352)
   - Arguments: (self)
29. **test_views.py** (Line 459)
   - Arguments: (self)
30. **test_views.py** (Line 569)
   - Arguments: (self)
31. **test_views.py** (Line 675)
   - Arguments: (self)
32. **test_views.py** (Line 760)
   - Arguments: (self)
33. **test_views.py** (Line 855)
   - Arguments: (self)
34. **test_views.py** (Line 949)
   - Arguments: (self)
35. **test_views.py** (Line 1022)
   - Arguments: (self)
36. **tests\test_incident_service.py** (Line 26)
   - Arguments: (self)
37. **tests\test_middleware.py** (Line 29)
   - Arguments: (self)
38. **tests\test_middleware.py** (Line 113)
   - Arguments: (self)
39. **tests\test_middleware.py** (Line 272)
   - Arguments: (self)
40. **tests\test_middleware.py** (Line 462)
   - Arguments: (self)
41. **tests\test_middleware.py** (Line 696)
   - Arguments: (self)
42. **tests\test_password_policy.py** (Line 26)
   - Arguments: (self)
43. **tests\test_security_insight.py** (Line 26)
   - Arguments: (self)
44. **tests\test_security_models.py** (Line 37)
   - Arguments: (self)
45. **tests\test_security_models.py** (Line 107)
   - Arguments: (self)
46. **tests\test_security_models.py** (Line 148)
   - Arguments: (self)
47. **tests\test_security_models.py** (Line 196)
   - Arguments: (self)
48. **tests\test_security_models.py** (Line 247)
   - Arguments: (self)
49. **tests\test_security_models.py** (Line 291)
   - Arguments: (self)
50. **tests\test_security_models.py** (Line 340)
   - Arguments: (self)
51. **tests\test_security_models.py** (Line 401)
   - Arguments: (self)
52. **tests\test_security_models.py** (Line 441)
   - Arguments: (self)
53. **tests\test_security_models.py** (Line 479)
   - Arguments: (self)
54. **tests\test_security_models.py** (Line 521)
   - Arguments: (self)
55. **tests\test_security_models.py** (Line 573)
   - Arguments: (self)
56. **tests\test_security_models.py** (Line 621)
   - Arguments: (self)
57. **tests\test_security_models.py** (Line 662)
   - Arguments: (self)
58. **tests\test_security_models.py** (Line 696)
   - Arguments: (self)
59. **tests\test_security_models.py** (Line 735)
   - Arguments: (self)
60. **tests\test_security_models.py** (Line 791)
   - Arguments: (self)
61. **tests\test_security_models.py** (Line 831)
   - Arguments: (self)
62. **tests\test_security_models.py** (Line 856)
   - Arguments: (self)
63. **tests\test_security_models.py** (Line 890)
   - Arguments: (self)
64. **tests\test_security_models.py** (Line 916)
   - Arguments: (self)
65. **tests\test_security_models.py** (Line 955)
   - Arguments: (self)
66. **tests\test_security_models.py** (Line 1003)
   - Arguments: (self)
67. **tests\test_security_models.py** (Line 1051)
   - Arguments: (self)
68. **tests\test_security_policy.py** (Line 26)
   - Arguments: (self)
69. **tests\test_security_views.py** (Line 38)
   - Arguments: (self)
70. **tests\test_security_views.py** (Line 168)
   - Arguments: (self)
71. **tests\test_security_views.py** (Line 300)
   - Arguments: (self)
72. **tests\test_security_views.py** (Line 416)
   - Arguments: (self)
73. **tests\test_security_views.py** (Line 529)
   - Arguments: (self)
74. **tests\test_security_views.py** (Line 668)
   - Arguments: (self)
75. **tests\test_security_views.py** (Line 811)
   - Arguments: (self)
76. **tests\test_security_views.py** (Line 926)
   - Arguments: (self)
77. **tests\test_security_views.py** (Line 1025)
   - Arguments: (self)
78. **tests\test_security_views.py** (Line 1170)
   - Arguments: (self)
79. **tests\test_security_views.py** (Line 1296)
   - Arguments: (self)
80. **tests\test_threat_intel.py** (Line 26)
   - Arguments: (self)
81. **tests\test_threat_intel.py** (Line 649)
   - Arguments: (self)
82. **tests\test_trusted_device.py** (Line 26)
   - Arguments: (self)
83. **tests\test_vpn_detector.py** (Line 25)
   - Arguments: (self)
84. **tests\test_vpn_detector.py** (Line 486)
   - Arguments: (self)
85. **tests\test_vpn_detector.py** (Line 549)
   - Arguments: (self)
86. **tests\test_vpn_detector.py** (Line 638)
   - Arguments: (self)

### set_alert_threshold

1. **integration_system\health_check.py** (Line 114)
   - Arguments: (self, metric_name, min_threshold, max_threshold)
2. **integration_system\performance_monitor.py** (Line 203)
   - Arguments: (self, metric_name, min_threshold, max_threshold)

### set_config

1. **abstracts.py** (Line 133)
   - Arguments: (self, config)
2. **abstracts.py** (Line 155)
   - Arguments: (self, config)
3. **abstracts.py** (Line 186)
   - Arguments: (self, config)
4. **abstracts.py** (Line 208)
   - Arguments: (self, config)
5. **abstracts.py** (Line 236)
   - Arguments: (self, config)
6. **abstracts.py** (Line 258)
   - Arguments: (self, config)
7. **abstracts.py** (Line 280)
   - Arguments: (self, config)
8. **abstracts.py** (Line 302)
   - Arguments: (self, config)
9. **abstracts.py** (Line 435)
   - Arguments: (self, config)
10. **abstracts.py** (Line 466)
   - Arguments: (self, config)
11. **abstracts.py** (Line 488)
   - Arguments: (self, config)
12. **abstracts.py** (Line 556)
   - Arguments: (self, config)
13. **abstracts.py** (Line 588)
   - Arguments: (self, config)
14. **abstracts.py** (Line 610)
   - Arguments: (self, config)
15. **abstracts.py** (Line 632)
   - Arguments: (self, config)
16. **hooks.py** (Line 80)
   - Arguments: (self, config)
17. **plugins.py** (Line 60)
   - Arguments: (self, config)
18. **signals_cap.py** (Line 282)
   - Arguments: (self, config)
19. **tasks_cap.py** (Line 63)
   - Arguments: (self, config)

### set_many

1. **caching.py** (Line 159)
   - Arguments: (self, data, ttl)
2. **utils\cache_manager.py** (Line 280)
   - Arguments: (data, timeout)

### set_priority

1. **hooks.py** (Line 76)
   - Arguments: (self, priority)
2. **model_mixins.py** (Line 369)
   - Arguments: (self, priority)

### should_trigger

1. **models.py** (Line 1694)
   - Arguments: (self)
2. **webhooks.py** (Line 112)
   - Arguments: (self, event_type)

### start

1. **monitoring.py** (Line 65)
   - Arguments: (self)
2. **views.py** (Line 2598)
   - Arguments: (self, request, pk)

### statistics

1. **views.py** (Line 1798)
   - Arguments: (self, request)
2. **views.py** (Line 2276)
   - Arguments: (self, request)
3. **views.py** (Line 10137)
   - Arguments: (self, request)
4. **viewset.py** (Line 120)
   - Arguments: (self, request)

### stats

1. **views.py** (Line 4278)
   - Arguments: (self, request)
2. **views.py** (Line 5376)
   - Arguments: (self, request)
3. **views.py** (Line 6215)
   - Arguments: (self, request)
4. **views.py** (Line 7281)
   - Arguments: (self, request)

### status_badge

1. **admin.py** (Line 2528)
   - Arguments: (self, obj)
2. **admin.py** (Line 3200)
   - Arguments: (self, obj)
3. **admin.py** (Line 4039)
   - Arguments: (self, obj)
4. **admin.py** (Line 4452)
   - Arguments: (self, obj)
5. **admin.py** (Line 5367)
   - Arguments: (self, obj)
6. **admin.py** (Line 5642)
   - Arguments: (self, obj)

### status_indicator

1. **admin.py** (Line 1345)
   - Arguments: (self, obj)
2. **admin.py** (Line 2041)
   - Arguments: (self, obj)
3. **admin.py** (Line 2840)
   - Arguments: (self, obj)
4. **admin.py** (Line 5118)
   - Arguments: (self, obj)
5. **admin.py** (Line 5946)
   - Arguments: (self, obj)
6. **admin.py** (Line 6257)
   - Arguments: (self, obj)

### stop

1. **monitoring.py** (Line 77)
   - Arguments: (self)
2. **views.py** (Line 2631)
   - Arguments: (self, request, pk)

### subscribe

1. **viewset.py** (Line 453)
   - Arguments: (self, request)
2. **integration_system\event_bus.py** (Line 177)
   - Arguments: (self, subscriber)

### summary

1. **views.py** (Line 8409)
   - Arguments: (self, request, pk)
2. **views.py** (Line 10633)
   - Arguments: (self, request)

### suspicious_activity

1. **views.py** (Line 4634)
   - Arguments: (self, request)
2. **views.py** (Line 10276)
   - Arguments: (self, request)

### tearDown

1. **tests.py** (Line 319)
   - Arguments: (self)
2. **tests.py** (Line 1448)
   - Arguments: (self)
3. **tests.py** (Line 1706)
   - Arguments: (self)

### test

1. **views.py** (Line 2216)
   - Arguments: (self, request, pk)
2. **views.py** (Line 2367)
   - Arguments: (self, request, pk)

### test_analyze_policy_violations

1. **tests\test_password_policy.py** (Line 902)
   - Arguments: (self)
2. **tests\test_security_policy.py** (Line 438)
   - Arguments: (self)

### test_calculate_performance_metrics

1. **tests\test_incident_service.py** (Line 1033)
   - Arguments: (self)
2. **tests\test_security_insight.py** (Line 424)
   - Arguments: (self)

### test_connection

1. **dependencies.py** (Line 72)
   - Arguments: (self)
2. **dependencies.py** (Line 109)
   - Arguments: (self)
3. **dependencies.py** (Line 272)
   - Arguments: (self)
4. **dependencies.py** (Line 390)
   - Arguments: (self)
5. **dependencies.py** (Line 500)
   - Arguments: (self)

### test_device_info_creation

1. **test_models.py** (Line 35)
   - Arguments: (self)
2. **tests\test_security_models.py** (Line 41)
   - Arguments: (self)

### test_export_insights

1. **tests\test_security_insight.py** (Line 779)
   - Arguments: (self)
2. **tests\test_security_views.py** (Line 1257)
   - Arguments: (self)

### test_export_password_history

1. **tests\test_password_policy.py** (Line 546)
   - Arguments: (self)
2. **tests\test_security_views.py** (Line 1003)
   - Arguments: (self)

### test_export_policies

1. **tests\test_security_policy.py** (Line 653)
   - Arguments: (self)
2. **tests\test_security_views.py** (Line 1143)
   - Arguments: (self)

### test_export_threat_intelligence

1. **tests\test_security_views.py** (Line 639)
   - Arguments: (self)
2. **tests\test_threat_intel.py** (Line 523)
   - Arguments: (self)

### test_function

1. **tests\test_vpn_detector.py** (Line 555)
   - Arguments: (ip_address)
2. **tests\test_vpn_detector.py** (Line 570)
   - Arguments: (ip_address)
3. **tests\test_vpn_detector.py** (Line 586)
4. **tests\test_vpn_detector.py** (Line 597)
   - Arguments: (ip_address)
5. **tests\test_vpn_detector.py** (Line 611)
   - Arguments: (ip_address)
6. **tests\test_vpn_detector.py** (Line 623)
   - Arguments: (ip_address)

### test_generate_compliance_report

1. **tests\test_password_policy.py** (Line 728)
   - Arguments: (self)
2. **tests\test_security_policy.py** (Line 1368)
   - Arguments: (self)

### test_generate_optimization_suggestions

1. **tests\test_incident_service.py** (Line 2064)
   - Arguments: (self)
2. **tests\test_password_policy.py** (Line 1301)
   - Arguments: (self)
3. **tests\test_security_policy.py** (Line 1062)
   - Arguments: (self)

### test_import_policies

1. **tests\test_security_policy.py** (Line 709)
   - Arguments: (self)
2. **tests\test_security_views.py** (Line 1151)
   - Arguments: (self)

### test_import_threat_intelligence

1. **tests\test_security_views.py** (Line 647)
   - Arguments: (self)
2. **tests\test_threat_intel.py** (Line 541)
   - Arguments: (self)

### test_risk_score_creation

1. **test_models.py** (Line 575)
   - Arguments: (self)
2. **tests\test_security_models.py** (Line 525)
   - Arguments: (self)

### test_security_incident_creation

1. **test_models.py** (Line 300)
   - Arguments: (self)
2. **tests\test_security_models.py** (Line 348)
   - Arguments: (self)

### test_security_insight_creation

1. **test_models.py** (Line 482)
   - Arguments: (self)
2. **tests\test_security_models.py** (Line 482)
   - Arguments: (self)

### test_security_log_creation

1. **tests.py** (Line 1714)
   - Arguments: (self)
2. **test_models.py** (Line 126)
   - Arguments: (self)
3. **tests\test_security_models.py** (Line 152)
   - Arguments: (self)

### test_security_policy_creation

1. **test_models.py** (Line 436)
   - Arguments: (self)
2. **tests\test_security_models.py** (Line 445)
   - Arguments: (self)

### test_threat_intelligence_confidence_validation

1. **test_views.py** (Line 407)
   - Arguments: (self)
2. **tests\test_security_models.py** (Line 308)
   - Arguments: (self)

### test_threat_intelligence_creation

1. **test_models.py** (Line 235)
   - Arguments: (self)
2. **tests\test_security_models.py** (Line 294)
   - Arguments: (self)

### test_threat_intelligence_workflow

1. **tests\test_security_models.py** (Line 1102)
   - Arguments: (self)
2. **tests\test_security_views.py** (Line 1372)
   - Arguments: (self)
3. **tests\test_threat_intel.py** (Line 655)
   - Arguments: (self)

### test_trusted_device_creation

1. **test_models.py** (Line 378)
   - Arguments: (self)
2. **tests\test_security_models.py** (Line 111)
   - Arguments: (self)

### test_user_ban_creation

1. **test_models.py** (Line 185)
   - Arguments: (self)
2. **tests\test_security_models.py** (Line 204)
   - Arguments: (self)

### test_user_session_creation

1. **test_models.py** (Line 624)
   - Arguments: (self)
2. **tests\test_security_models.py** (Line 625)
   - Arguments: (self)

### test_vpn_detection_basic

1. **tests.py** (Line 2230)
   - Arguments: (self)
2. **tests\test_middleware.py** (Line 469)
   - Arguments: (self, mock_detector_class)

### to_dict

1. **abstracts.py** (Line 34)
   - Arguments: (self)
2. **encryption.py** (Line 55)
   - Arguments: (self)
3. **events.py** (Line 39)
   - Arguments: (self)
4. **exceptions.py** (Line 72)
   - Arguments: (self)
5. **exceptions.py** (Line 133)
   - Arguments: (self)
6. **exceptions.py** (Line 192)
   - Arguments: (self)
7. **exceptions.py** (Line 248)
   - Arguments: (self)
8. **schemas.py** (Line 26)
   - Arguments: (self)
9. **webhooks.py** (Line 39)
   - Arguments: (self)
10. **integration_system\event_bus.py** (Line 47)
   - Arguments: (self)
11. **integration_system\integ_exceptions.py** (Line 24)
   - Arguments: (self)
12. **integration_system\message_queue.py** (Line 45)
   - Arguments: (self)
13. **integration_system\versioning.py** (Line 35)
   - Arguments: (self)

### to_representation

1. **serializers.py** (Line 4559)
   - Arguments: (self, instance)
2. **serializers.py** (Line 7661)
   - Arguments: (self, instance)
3. **serializers.py** (Line 8404)
   - Arguments: (self, instance)
4. **serializers.py** (Line 8582)
   - Arguments: (self, instance)
5. **serializers.py** (Line 8637)
   - Arguments: (self, instance)
6. **serializers.py** (Line 9434)
   - Arguments: (self, instance)
7. **serializers.py** (Line 10235)
   - Arguments: (self, instance)
8. **serializers.py** (Line 10449)
   - Arguments: (self, instance)
9. **serializers.py** (Line 11615)
   - Arguments: (self, instance)

### toggle_active

1. **views.py** (Line 8430)
   - Arguments: (self, request, pk)
2. **views.py** (Line 9329)
   - Arguments: (self, request, pk)

### transform

1. **abstracts.py** (Line 293)
   - Arguments: (self, data, target_format)
2. **integration_system\transformer.py** (Line 55)
   - Arguments: (self, data)

### trusted

1. **managers.py** (Line 384)
   - Arguments: (self)
2. **querysets.py** (Line 227)
   - Arguments: (self)

### type_badge

1. **admin.py** (Line 867)
   - Arguments: (self, obj)
2. **admin.py** (Line 5098)
   - Arguments: (self, obj)

### unassigned

1. **managers.py** (Line 195)
   - Arguments: (self)
2. **querysets.py** (Line 384)
   - Arguments: (self)

### unregister

1. **endpoint.py** (Line 189)
   - Arguments: (self, name)
2. **registry.py** (Line 118)
   - Arguments: (self, name)
3. **resources.py** (Line 492)
   - Arguments: (self, name)

### unregister_adapter

1. **integration_system\integ_adapter.py** (Line 509)
   - Arguments: (self, adapter_name)
2. **integration_system\integ_registry.py** (Line 91)
   - Arguments: (self, adapter_name)

### unregister_handler

1. **events.py** (Line 342)
   - Arguments: (self, pattern, handler)
2. **integration_system\integ_exceptions.py** (Line 402)
   - Arguments: (self, exception_type)

### unregister_integration

1. **integration_system\integ_handler.py** (Line 43)
   - Arguments: (self, integration_name)
2. **integration_system\integ_registry.py** (Line 56)
   - Arguments: (self, integration_name)

### unsubscribe

1. **viewset.py** (Line 475)
   - Arguments: (self, request)
2. **integration_system\event_bus.py** (Line 187)
   - Arguments: (self, subscriber_name)

### untrusted

1. **managers.py** (Line 388)
   - Arguments: (self)
2. **querysets.py** (Line 231)
   - Arguments: (self)

### update

1. **abstracts.py** (Line 325)
   - Arguments: (self, id, data)
2. **repositories.py** (Line 52)
   - Arguments: (self, id)
3. **serializers.py** (Line 4507)
   - Arguments: (self, instance, validated_data)
4. **serializers.py** (Line 4793)
   - Arguments: (self, instance, validated_data)
5. **serializers.py** (Line 5189)
   - Arguments: (self, instance, validated_data)
6. **serializers.py** (Line 5586)
   - Arguments: (self, instance, validated_data)
7. **serializers.py** (Line 5745)
   - Arguments: (self, instance, validated_data)
8. **serializers.py** (Line 6290)
   - Arguments: (self, instance, validated_data)
9. **serializers.py** (Line 7036)
   - Arguments: (self, instance, validated_data)
10. **serializers.py** (Line 7172)
   - Arguments: (self, instance, validated_data)
11. **serializers.py** (Line 7510)
   - Arguments: (self, instance, validated_data)
12. **serializers.py** (Line 7995)
   - Arguments: (self, instance, validated_data)
13. **serializers.py** (Line 9350)
   - Arguments: (self, instance, validated_data)
14. **serializers.py** (Line 10161)
   - Arguments: (self, instance, validated_data)
15. **serializers.py** (Line 11541)
   - Arguments: (self, instance, validated_data)
16. **views.py** (Line 1031)
   - Arguments: (self, request)
17. **viewset.py** (Line 264)
   - Arguments: (self, request)

### update_limits

1. **models.py** (Line 8001)
   - Arguments: (self, daily_limit, weekly_limit, monthly_limit, single_transaction_limit, updated_by)
2. **views.py** (Line 8254)
   - Arguments: (self, request, pk)

### update_statistics

1. **admin.py** (Line 2628)
   - Arguments: (self, obj)
2. **models.py** (Line 1964)
   - Arguments: (self)
3. **serializers.py** (Line 10515)
   - Arguments: (self, instance)
4. **views.py** (Line 9061)
   - Arguments: (self, request, pk)

### update_status

1. **model_mixins.py** (Line 198)
   - Arguments: (self, new_status, user)
2. **resources.py** (Line 88)
   - Arguments: (self, status, response_time)
3. **integration_system\health_check.py** (Line 47)
   - Arguments: (self, status, metrics)

### user_activity

1. **views.py** (Line 4374)
   - Arguments: (self, request)
2. **views.py** (Line 10193)
   - Arguments: (self, request)
3. **viewset.py** (Line 313)
   - Arguments: (self, request)

### user_display

1. **admin.py** (Line 155)
   - Arguments: (self, obj)
2. **admin.py** (Line 1302)
   - Arguments: (self, obj)
3. **admin.py** (Line 3183)
   - Arguments: (self, obj)
4. **admin.py** (Line 3596)
   - Arguments: (self, obj)
5. **admin.py** (Line 4018)
   - Arguments: (self, obj)
6. **admin.py** (Line 4474)
   - Arguments: (self, obj)
7. **admin.py** (Line 4584)
   - Arguments: (self, obj)
8. **admin.py** (Line 4659)
   - Arguments: (self, obj)
9. **admin.py** (Line 5341)
   - Arguments: (self, obj)
10. **admin.py** (Line 5623)
   - Arguments: (self, obj)

### user_link

1. **admin.py** (Line 848)
   - Arguments: (self, obj)
2. **admin.py** (Line 1723)
   - Arguments: (self, obj)

### validate

1. **abstracts.py** (Line 124)
   - Arguments: (self, data, rules)
2. **serializers.py** (Line 3382)
   - Arguments: (self, data)
3. **serializers.py** (Line 4374)
   - Arguments: (self, data)
4. **serializers.py** (Line 4764)
   - Arguments: (self, data)
5. **serializers.py** (Line 4969)
   - Arguments: (self, data)
6. **serializers.py** (Line 5165)
   - Arguments: (self, data)
7. **serializers.py** (Line 5497)
   - Arguments: (self, data)
8. **serializers.py** (Line 5707)
   - Arguments: (self, data)
9. **serializers.py** (Line 5808)
   - Arguments: (self, data)
10. **serializers.py** (Line 6184)
   - Arguments: (self, data)
11. **serializers.py** (Line 6542)
   - Arguments: (self, data)
12. **serializers.py** (Line 6968)
   - Arguments: (self, data)
13. **serializers.py** (Line 7153)
   - Arguments: (self, data)
14. **serializers.py** (Line 7235)
   - Arguments: (self, data)
15. **serializers.py** (Line 7432)
   - Arguments: (self, data)
16. **serializers.py** (Line 7553)
   - Arguments: (self, data)
17. **serializers.py** (Line 7632)
   - Arguments: (self, data)
18. **serializers.py** (Line 7881)
   - Arguments: (self, attrs)
19. **serializers.py** (Line 8060)
   - Arguments: (self, attrs)
20. **serializers.py** (Line 8115)
   - Arguments: (self, attrs)
21. **serializers.py** (Line 8333)
   - Arguments: (self, data)
22. **serializers.py** (Line 9090)
   - Arguments: (self, attrs)
23. **serializers.py** (Line 9956)
   - Arguments: (self, attrs)
24. **serializers.py** (Line 10325)
   - Arguments: (self, data)
25. **serializers.py** (Line 10623)
   - Arguments: (self, attrs)
26. **serializers.py** (Line 10720)
   - Arguments: (self, attrs)
27. **serializers.py** (Line 10921)
   - Arguments: (self, attrs)
28. **serializers.py** (Line 11336)
   - Arguments: (self, attrs)
29. **serializers.py** (Line 11705)
   - Arguments: (self, data)
30. **integration_system\data_validator.py** (Line 35)
   - Arguments: (self, value, context)
31. **integration_system\data_validator.py** (Line 59)
   - Arguments: (self, value, context)
32. **integration_system\data_validator.py** (Line 71)
   - Arguments: (self, value, context)
33. **integration_system\data_validator.py** (Line 90)
   - Arguments: (self, value, context)
34. **integration_system\data_validator.py** (Line 114)
   - Arguments: (self, value, context)
35. **integration_system\data_validator.py** (Line 154)
   - Arguments: (self, value, context)
36. **integration_system\data_validator.py** (Line 187)
   - Arguments: (self, value, context)
37. **integration_system\data_validator.py** (Line 218)
   - Arguments: (self, value, context)
38. **integration_system\data_validator.py** (Line 230)
   - Arguments: (self, value, context)
39. **integration_system\data_validator.py** (Line 284)
   - Arguments: (self, data, context)

### validate_app_version

1. **decorators.py** (Line 216)
2. **serializers.py** (Line 274)

### validate_ban_consistency

1. **models.py** (Line 3414)
   - Arguments: (sender, instance)
2. **serializers.py** (Line 5325)
   - Arguments: (self, data)

### validate_config

1. **plugins.py** (Line 56)
   - Arguments: (self, config)
2. **integration_system\integ_handler.py** (Line 333)
   - Arguments: (self)

### validate_input

1. **interactors.py** (Line 40)
   - Arguments: (self, data)
2. **use_cases.py** (Line 36)
   - Arguments: (self, data)

### validate_ip_address

1. **models.py** (Line 4593)
   - Arguments: (ip_address)
2. **serializers.py** (Line 3168)
   - Arguments: (ip)
3. **serializers.py** (Line 3615)
   - Arguments: (ip_address)
4. **serializers.py** (Line 3831)
   - Arguments: (ip)
5. **serializers.py** (Line 4370)
   - Arguments: (self, ip)
6. **serializers.py** (Line 10569)
   - Arguments: (self, value)
7. **views.py** (Line 5774)
   - Arguments: (ip_address)
8. **utils\security_helpers.py** (Line 461)
   - Arguments: (ip_address)

### validate_password

1. **models.py** (Line 2460)
   - Arguments: (self, password, username)
2. **views.py** (Line 9380)
   - Arguments: (self, request)

### validate_password_strength

1. **utils.py** (Line 342)
   - Arguments: (password)
2. **validators.py** (Line 37)
   - Arguments: (password, user)

### validate_phone_number

1. **serializers.py** (Line 10842)
   - Arguments: (self, value)
2. **utils.py** (Line 224)
   - Arguments: (phone)

### validate_request

1. **abstracts.py** (Line 396)
   - Arguments: (self, request_data)
2. **decorators.py** (Line 363)
   - Arguments: (func)
3. **decorators.py** (Line 1073)
   - Arguments: (required_params, allowed_methods, schema_validator)

### validate_request_params

1. **decorators.py** (Line 68)
   - Arguments: (required_params, optional_params)
2. **serializers.py** (Line 129)
   - Arguments: (required_params, optional_params)

### validate_token

1. **endpoint.py** (Line 358)
   - Arguments: (request)
2. **integration_system\auth_bridge.py** (Line 293)
   - Arguments: (self, token)

### verify

1. **encryption.py** (Line 370)
   - Arguments: (self, data, signature)
2. **model_mixins.py** (Line 305)
   - Arguments: (self, user)
3. **serializers.py** (Line 2574)
   - Arguments: (self, request)

### verify_password

1. **encryption.py** (Line 601)
   - Arguments: (self, password, hashed_password, salt)
2. **utils.py** (Line 50)
   - Arguments: (password, salt, stored_hash)

### verify_signature

1. **encryption.py** (Line 566)
   - Arguments: (self, data, signature, public_key_pem)
2. **integration_system\webhooks_integration.py** (Line 262)
   - Arguments: (self, payload, signature, secret, algorithm)

### wait

1. **throttling.py** (Line 143)
   - Arguments: (self)
2. **throttling.py** (Line 438)
   - Arguments: (self)

### with_default

1. **models.py** (Line 106)
   - Arguments: (default_value)
2. **models.py** (Line 3484)
   - Arguments: (cls, default_value)

### wrapped

1. **utils\device.py** (Line 754)
2. **utils\device.py** (Line 825)
   - Arguments: (self)

### wrapped_view

1. **permissions_backup.py** (Line 621)
   - Arguments: (request)
2. **permissions_backup.py** (Line 643)
   - Arguments: (request)

### wrapper

1. **admin.py** (Line 6711)
   - Arguments: (self, request)
2. **admin.py** (Line 7079)
   - Arguments: (request)
3. **admin.py** (Line 7087)
   - Arguments: (request)
4. **admin.py** (Line 73)
   - Arguments: (self, obj)
5. **admin.py** (Line 89)
   - Arguments: (self, request, queryset)
6. **admin.py** (Line 6749)
7. **caching.py** (Line 611)
8. **common_imports.py** (Line 239)
9. **common_imports.py** (Line 254)
10. **common_imports.py** (Line 268)
   - Arguments: (request)
11. **decorators.py** (Line 368)
   - Arguments: (request)
12. **decorators.py** (Line 36)
   - Arguments: (request)
13. **decorators.py** (Line 74)
   - Arguments: (request)
14. **decorators.py** (Line 130)
   - Arguments: (request)
15. **decorators.py** (Line 194)
   - Arguments: (request)
16. **decorators.py** (Line 222)
   - Arguments: (request)
17. **decorators.py** (Line 273)
   - Arguments: (request)
18. **decorators.py** (Line 402)
   - Arguments: (request)
19. **decorators.py** (Line 448)
   - Arguments: (request)
20. **decorators.py** (Line 492)
   - Arguments: (self, request)
21. **decorators.py** (Line 536)
22. **decorators.py** (Line 554)
23. **decorators.py** (Line 590)
   - Arguments: (request)
24. **decorators.py** (Line 650)
   - Arguments: (request)
25. **decorators.py** (Line 787)
   - Arguments: (self, request)
26. **decorators.py** (Line 910)
   - Arguments: (request)
27. **decorators.py** (Line 1000)
   - Arguments: (request)
28. **decorators.py** (Line 1083)
   - Arguments: (request)
29. **decorators.py** (Line 1320)
30. **decorators.py** (Line 1393)
   - Arguments: (self)
31. **exceptions.py** (Line 609)
32. **exceptions.py** (Line 626)
33. **feature_flags.py** (Line 702)
34. **models.py** (Line 121)
   - Arguments: (self)
35. **models.py** (Line 3474)
36. **models.py** (Line 108)
37. **permissions.py** (Line 410)
   - Arguments: (request)
38. **permissions.py** (Line 427)
   - Arguments: (request)
39. **serializers.py** (Line 98)
   - Arguments: (request)
40. **serializers.py** (Line 135)
   - Arguments: (request)
41. **serializers.py** (Line 190)
   - Arguments: (request)
42. **serializers.py** (Line 253)
   - Arguments: (request)
43. **serializers.py** (Line 280)
   - Arguments: (request)
44. **serializers.py** (Line 3657)
   - Arguments: (self, obj)
45. **serializers.py** (Line 3671)
   - Arguments: (self, obj)
46. **serializers.py** (Line 3762)
47. **tests.py** (Line 263)
48. **tests.py** (Line 278)
49. **views.py** (Line 375)
50. **views.py** (Line 300)
   - Arguments: (self)
51. **views.py** (Line 335)
   - Arguments: (self, request)
52. **views.py** (Line 425)
   - Arguments: (self, request)
53. **views.py** (Line 455)
   - Arguments: (self, request)
54. **views.py** (Line 486)
   - Arguments: (self, request)
55. **integration_system\circuit_breaker.py** (Line 348)
56. **utils\cache_manager.py** (Line 335)
57. **utils\cache_manager.py** (Line 439)
   - Arguments: (self)
58. **utils\cache_manager.py** (Line 585)
59. **utils\cache_manager.py** (Line 627)

## 📦 Duplicate Imports (A-Z)

### abc.ABC

1. **abstracts.py** (Line 7)
   - From module: abc
2. **dependencies.py** (Line 16)
   - From module: abc
3. **plugins.py** (Line 13)
   - From module: abc

### abc.abstractmethod

1. **abstracts.py** (Line 7)
   - From module: abc
2. **dependencies.py** (Line 16)
   - From module: abc
3. **plugins.py** (Line 13)
   - From module: abc

### analytics.security_analytics

1. **data_export.py** (Line 756)
   - From module: analytics
2. **data_export.py** (Line 769)
   - From module: analytics
3. **data_export.py** (Line 837)
   - From module: analytics
4. **signals_cap.py** (Line 21)
   - From module: analytics
5. **tasks_cap.py** (Line 23)
   - From module: analytics

### api.fraud_detection.models.IPReputation

1. **services.py** (Line 129)
   - From module: api.fraud_detection.models
2. **signals.py** (Line 540)
   - From module: api.fraud_detection.models
3. **services\ThreatIntelService.py** (Line 135)
   - From module: api.fraud_detection.models

### api.security.choices.IncidentStatus

1. **services\IncidentService.py** (Line 19)
   - From module: api.security.choices
2. **services\IncidentService.py** (Line 477)
   - From module: api.security.choices
3. **services\IncidentService.py** (Line 264)
   - From module: api.security.choices
4. **services\IncidentService.py** (Line 384)
   - From module: api.security.choices

### api.security.constants.CacheSettings

1. **services\IncidentService.py** (Line 18)
   - From module: api.security.constants
2. **services\ThreatIntelService.py** (Line 21)
   - From module: api.security.constants

### api.security.middleware.RateLimitMiddleware

1. **tests.py** (Line 43)
   - From module: api.security.middleware
2. **tests\test_middleware.py** (Line 17)
   - From module: api.security.middleware

### api.security.middleware.SecurityAuditMiddleware

1. **tests.py** (Line 43)
   - From module: api.security.middleware
2. **tests\test_middleware.py** (Line 17)
   - From module: api.security.middleware

### api.security.middleware.SecurityHeadersMiddleware

1. **tests.py** (Line 43)
   - From module: api.security.middleware
2. **tests\test_middleware.py** (Line 17)
   - From module: api.security.middleware

### api.security.middleware.VPNProxyDetectionMiddleware

1. **tests.py** (Line 43)
   - From module: api.security.middleware
2. **tests\test_middleware.py** (Line 17)
   - From module: api.security.middleware

### api.security.models.APIRateLimit

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models
3. **tests.py** (Line 38)
   - From module: api.security.models

### api.security.models.AlertRule

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.AppVersion

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.AuditTrail

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.AutoBlockRule

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models
3. **tests.py** (Line 38)
   - From module: api.security.models

### api.security.models.ClickTracker

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models
3. **utils\device.py** (Line 8)
   - From module: api.security.models

### api.security.models.Country

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.CountryBlockRule

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.DataExport

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.DataImport

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.DeviceInfo

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models
3. **tasks.py** (Line 19)
   - From module: api.security.models
4. **tests.py** (Line 24)
   - From module: api.security.models
5. **tests.py** (Line 38)
   - From module: api.security.models
6. **management\commands\block_suspicious_ips.py** (Line 18)
   - From module: api.security.models
7. **management\commands\export_security_report.py** (Line 21)
   - From module: api.security.models
8. **management\commands\run_security_scan.py** (Line 21)
   - From module: api.security.models
9. **management\commands\seed_security_rules.py** (Line 17)
   - From module: api.security.models
10. **utils\device.py** (Line 8)
   - From module: api.security.models

### api.security.models.FraudPattern

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models
3. **tests.py** (Line 38)
   - From module: api.security.models

### api.security.models.GeolocationLog

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models
3. **tests.py** (Line 38)
   - From module: api.security.models

### api.security.models.IPBlacklist

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models
3. **tasks.py** (Line 19)
   - From module: api.security.models
4. **tests.py** (Line 38)
   - From module: api.security.models
5. **management\commands\block_suspicious_ips.py** (Line 18)
   - From module: api.security.models
6. **management\commands\export_security_report.py** (Line 21)
   - From module: api.security.models
7. **management\commands\run_security_scan.py** (Line 21)
   - From module: api.security.models
8. **management\commands\seed_security_rules.py** (Line 17)
   - From module: api.security.models
9. **services\SecurityInsightService.py** (Line 18)
   - From module: api.security.models

### api.security.models.MaintenanceMode

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.PasswordAttempt

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.PasswordHistory

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models
3. **tasks.py** (Line 19)
   - From module: api.security.models
4. **management\commands\export_security_report.py** (Line 21)
   - From module: api.security.models
5. **management\commands\seed_security_rules.py** (Line 17)
   - From module: api.security.models
6. **management\commands\unlock_user_accounts.py** (Line 18)
   - From module: api.security.models
7. **services\PasswordHistoryService.py** (Line 17)
   - From module: api.security.models

### api.security.models.PasswordPolicy

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.RateLimitLog

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.RealTimeDetection

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.RiskScore

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models
3. **tasks.py** (Line 19)
   - From module: api.security.models
4. **tests.py** (Line 38)
   - From module: api.security.models
5. **management\commands\block_suspicious_ips.py** (Line 18)
   - From module: api.security.models
6. **management\commands\export_security_report.py** (Line 21)
   - From module: api.security.models
7. **management\commands\run_security_scan.py** (Line 21)
   - From module: api.security.models
8. **management\commands\seed_security_rules.py** (Line 17)
   - From module: api.security.models
9. **management\commands\unlock_user_accounts.py** (Line 18)
   - From module: api.security.models

### api.security.models.SecurityConfig

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.SecurityDashboard

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models
3. **tests.py** (Line 38)
   - From module: api.security.models

### api.security.models.SecurityIncident

1. **admin.py** (Line 7676)
   - From module: api.security.models
2. **tasks.py** (Line 19)
   - From module: api.security.models
3. **management\commands\block_suspicious_ips.py** (Line 18)
   - From module: api.security.models
4. **management\commands\export_security_report.py** (Line 21)
   - From module: api.security.models
5. **management\commands\run_security_scan.py** (Line 21)
   - From module: api.security.models
6. **management\commands\seed_security_rules.py** (Line 17)
   - From module: api.security.models
7. **management\commands\unlock_user_accounts.py** (Line 18)
   - From module: api.security.models
8. **services\IncidentService.py** (Line 17)
   - From module: api.security.models

### api.security.models.SecurityInsight

1. **tasks.py** (Line 19)
   - From module: api.security.models
2. **management\commands\export_security_report.py** (Line 21)
   - From module: api.security.models
3. **management\commands\seed_security_rules.py** (Line 17)
   - From module: api.security.models
4. **services\SecurityInsightService.py** (Line 18)
   - From module: api.security.models

### api.security.models.SecurityLog

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models
3. **tasks.py** (Line 19)
   - From module: api.security.models
4. **tests.py** (Line 24)
   - From module: api.security.models
5. **tests.py** (Line 38)
   - From module: api.security.models
6. **management\commands\block_suspicious_ips.py** (Line 18)
   - From module: api.security.models
7. **management\commands\export_security_report.py** (Line 21)
   - From module: api.security.models
8. **management\commands\run_security_scan.py** (Line 21)
   - From module: api.security.models
9. **management\commands\seed_security_rules.py** (Line 17)
   - From module: api.security.models
10. **management\commands\unlock_user_accounts.py** (Line 18)
   - From module: api.security.models
11. **services\IncidentService.py** (Line 17)
   - From module: api.security.models
12. **services\PasswordHistoryService.py** (Line 172)
   - From module: api.security.models
13. **services\SecurityInsightService.py** (Line 18)
   - From module: api.security.models
14. **utils\device.py** (Line 8)
   - From module: api.security.models
15. **utils\security_helpers.py** (Line 437)
   - From module: api.security.models

### api.security.models.SecurityNotification

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.SecurityPolicy

1. **tasks.py** (Line 19)
   - From module: api.security.models
2. **management\commands\export_security_report.py** (Line 21)
   - From module: api.security.models
3. **management\commands\seed_security_rules.py** (Line 17)
   - From module: api.security.models
4. **services\PasswordHistoryService.py** (Line 258)
   - From module: api.security.models
5. **services\SecurityPolicyService.py** (Line 17)
   - From module: api.security.models

### api.security.models.SessionActivity

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.ThreatIntelligence

1. **admin.py** (Line 7676)
   - From module: api.security.models
2. **tasks.py** (Line 19)
   - From module: api.security.models
3. **management\commands\block_suspicious_ips.py** (Line 18)
   - From module: api.security.models
4. **management\commands\export_security_report.py** (Line 21)
   - From module: api.security.models
5. **management\commands\run_security_scan.py** (Line 21)
   - From module: api.security.models
6. **management\commands\seed_security_rules.py** (Line 17)
   - From module: api.security.models
7. **services\ThreatIntelService.py** (Line 20)
   - From module: api.security.models

### api.security.models.TrustedDevice

1. **tasks.py** (Line 19)
   - From module: api.security.models
2. **management\commands\export_security_report.py** (Line 21)
   - From module: api.security.models
3. **management\commands\run_security_scan.py** (Line 21)
   - From module: api.security.models
4. **management\commands\seed_security_rules.py** (Line 17)
   - From module: api.security.models
5. **management\commands\unlock_user_accounts.py** (Line 18)
   - From module: api.security.models
6. **services\TrustedDeviceService.py** (Line 17)
   - From module: api.security.models

### api.security.models.TwoFactorAttempt

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.TwoFactorMethod

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.TwoFactorRecoveryCode

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models

### api.security.models.UserBan

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **tasks.py** (Line 19)
   - From module: api.security.models
3. **tests.py** (Line 24)
   - From module: api.security.models
4. **tests.py** (Line 38)
   - From module: api.security.models
5. **management\commands\export_security_report.py** (Line 21)
   - From module: api.security.models
6. **management\commands\run_security_scan.py** (Line 21)
   - From module: api.security.models
7. **management\commands\seed_security_rules.py** (Line 17)
   - From module: api.security.models
8. **management\commands\unlock_user_accounts.py** (Line 18)
   - From module: api.security.models
9. **services\IncidentService.py** (Line 17)
   - From module: api.security.models
10. **services\SecurityInsightService.py** (Line 18)
   - From module: api.security.models

### api.security.models.UserSession

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models
3. **tests.py** (Line 38)
   - From module: api.security.models
4. **services\SecurityPolicyService.py** (Line 404)
   - From module: api.security.models

### api.security.models.WithdrawalProtection

1. **admin.py** (Line 26)
   - From module: api.security.models
2. **admin.py** (Line 7676)
   - From module: api.security.models
3. **utils\device.py** (Line 8)
   - From module: api.security.models

### api.security.services.IncidentService.IncidentService

1. **tasks.py** (Line 26)
   - From module: api.security.services.IncidentService
2. **management\commands\run_security_scan.py** (Line 20)
   - From module: api.security.services.IncidentService
3. **services\__init__.py** (Line 11)
   - From module: api.security.services.IncidentService
4. **tests\test_incident_service.py** (Line 16)
   - From module: api.security.services.IncidentService

### api.security.services.PasswordHistoryService.PasswordHistoryService

1. **services\__init__.py** (Line 13)
   - From module: api.security.services.PasswordHistoryService
2. **tests\test_password_policy.py** (Line 16)
   - From module: api.security.services.PasswordHistoryService

### api.security.services.SecurityInsightService.SecurityInsightService

1. **services\__init__.py** (Line 15)
   - From module: api.security.services.SecurityInsightService
2. **tests\test_security_insight.py** (Line 16)
   - From module: api.security.services.SecurityInsightService

### api.security.services.SecurityPolicyService.SecurityPolicyService

1. **services\__init__.py** (Line 14)
   - From module: api.security.services.SecurityPolicyService
2. **tests\test_security_policy.py** (Line 16)
   - From module: api.security.services.SecurityPolicyService

### api.security.services.ThreatIntelService.ThreatIntelService

1. **tasks.py** (Line 25)
   - From module: api.security.services.ThreatIntelService
2. **management\commands\run_security_scan.py** (Line 19)
   - From module: api.security.services.ThreatIntelService
3. **services\__init__.py** (Line 10)
   - From module: api.security.services.ThreatIntelService
4. **tests\test_threat_intel.py** (Line 16)
   - From module: api.security.services.ThreatIntelService

### api.security.services.TrustedDeviceService.TrustedDeviceService

1. **services\__init__.py** (Line 12)
   - From module: api.security.services.TrustedDeviceService
2. **tests\test_trusted_device.py** (Line 16)
   - From module: api.security.services.TrustedDeviceService

### api.security.utils.cache_manager.CacheManager

1. **services\IncidentService.py** (Line 20)
   - From module: api.security.utils.cache_manager
2. **services\PasswordHistoryService.py** (Line 18)
   - From module: api.security.utils.cache_manager
3. **services\SecurityInsightService.py** (Line 19)
   - From module: api.security.utils.cache_manager
4. **services\SecurityPolicyService.py** (Line 18)
   - From module: api.security.utils.cache_manager
5. **services\ThreatIntelService.py** (Line 23)
   - From module: api.security.utils.cache_manager
6. **services\TrustedDeviceService.py** (Line 18)
   - From module: api.security.utils.cache_manager

### api.security.utils.cache_manager.handle_gracefully

1. **services\IncidentService.py** (Line 20)
   - From module: api.security.utils.cache_manager
2. **services\PasswordHistoryService.py** (Line 18)
   - From module: api.security.utils.cache_manager
3. **services\SecurityInsightService.py** (Line 19)
   - From module: api.security.utils.cache_manager
4. **services\SecurityPolicyService.py** (Line 18)
   - From module: api.security.utils.cache_manager
5. **services\ThreatIntelService.py** (Line 23)
   - From module: api.security.utils.cache_manager
6. **services\TrustedDeviceService.py** (Line 18)
   - From module: api.security.utils.cache_manager

### api.security.utils.device.send_security_alert

1. **services\IncidentService.py** (Line 214)
   - From module: api.security.utils.device
2. **services\IncidentService.py** (Line 427)
   - From module: api.security.utils.device

### api.security.viewsets.DeviceInfoViewSet

1. **tests.py** (Line 26)
   - From module: api.security.viewsets
2. **tests\test_security_views.py** (Line 18)
   - From module: api.security.viewsets

### api.security.vpn_detector.VPNDetector

1. **tasks.py** (Line 24)
   - From module: api.security.vpn_detector
2. **tests.py** (Line 47)
   - From module: api.security.vpn_detector
3. **management\commands\block_suspicious_ips.py** (Line 22)
   - From module: api.security.vpn_detector
4. **management\commands\run_security_scan.py** (Line 18)
   - From module: api.security.vpn_detector
5. **tests\test_vpn_detector.py** (Line 15)
   - From module: api.security.vpn_detector

### api.security.vpn_detector.VPNServiceError

1. **tasks.py** (Line 24)
   - From module: api.security.vpn_detector
2. **management\commands\block_suspicious_ips.py** (Line 22)
   - From module: api.security.vpn_detector
3. **management\commands\run_security_scan.py** (Line 18)
   - From module: api.security.vpn_detector
4. **tests\test_vpn_detector.py** (Line 15)
   - From module: api.security.vpn_detector

### api.wallet.validators.is_valid_ipv4

1. **admin.py** (Line 941)
   - From module: api.wallet.validators
2. **admin.py** (Line 1085)
   - From module: api.wallet.validators

### api.wallet.validators.is_valid_ipv6

1. **admin.py** (Line 941)
   - From module: api.wallet.validators
2. **admin.py** (Line 1085)
   - From module: api.wallet.validators

### api.wallet.validators.safe_ip_address

1. **admin.py** (Line 1085)
   - From module: api.wallet.validators
2. **admin.py** (Line 1142)
   - From module: api.wallet.validators
3. **models.py** (Line 783)
   - From module: api.wallet.validators

### asyncio

1. **consumers.py** (Line 17)
   - From module: asyncio
2. **openai.py** (Line 10)
   - From module: asyncio
3. **integration_system\bridge.py** (Line 7)
   - From module: asyncio
4. **integration_system\data_bridge.py** (Line 7)
   - From module: asyncio
5. **integration_system\event_bus.py** (Line 7)
   - From module: asyncio
6. **integration_system\integ_handler.py** (Line 7)
   - From module: asyncio
7. **integration_system\message_queue.py** (Line 7)
   - From module: asyncio

### base64

1. **common_imports.py** (Line 15)
   - From module: base64
2. **dependencies.py** (Line 19)
   - From module: base64
3. **encryption.py** (Line 8)
   - From module: base64
4. **models.py** (Line 37)
   - From module: base64
5. **openai.py** (Line 19)
   - From module: base64
6. **pagination.py** (Line 220)
   - From module: base64
7. **pagination.py** (Line 246)
   - From module: base64

### celery.Task

1. **common_imports.py** (Line 98)
   - From module: celery
2. **tasks_cap.py** (Line 15)
   - From module: celery

### celery.result.AsyncResult

1. **common_imports.py** (Line 99)
   - From module: celery.result
2. **tasks_cap.py** (Line 16)
   - From module: celery.result

### celery.schedules.crontab

1. **celery_beat_config.py** (Line 8)
   - From module: celery.schedules
2. **common_imports.py** (Line 100)
   - From module: celery.schedules

### celery.shared_task

1. **common_imports.py** (Line 98)
   - From module: celery
2. **tasks_cap.py** (Line 15)
   - From module: celery

### circuit_breaker.circuit_breaker_protected

1. **integration_system\data_bridge.py** (Line 21)
   - From module: circuit_breaker
2. **integration_system\message_queue.py** (Line 21)
   - From module: circuit_breaker
3. **integration_system\webhooks_integration.py** (Line 29)
   - From module: circuit_breaker

### collections.defaultdict

1. **common_imports.py** (Line 24)
   - From module: collections
2. **duplicate_analyzer.py** (Line 10)
   - From module: collections
3. **views.py** (Line 10)
   - From module: collections
4. **management\commands\block_suspicious_ips.py** (Line 16)
   - From module: collections
5. **management\commands\export_security_report.py** (Line 19)
   - From module: collections
6. **management\commands\unlock_user_accounts.py** (Line 16)
   - From module: collections

### concurrent.futures.ThreadPoolExecutor

1. **tests.py** (Line 12)
   - From module: concurrent.futures
2. **tests.py** (Line 1174)
   - From module: concurrent.futures

### cryptography.fernet.Fernet

1. **common_imports.py** (Line 104)
   - From module: cryptography.fernet
2. **encryption.py** (Line 16)
   - From module: cryptography.fernet
3. **models.py** (Line 39)
   - From module: cryptography.fernet
4. **utils.py** (Line 18)
   - From module: cryptography.fernet

### cryptography.hazmat.backends.default_backend

1. **common_imports.py** (Line 108)
   - From module: cryptography.hazmat.backends
2. **encryption.py** (Line 22)
   - From module: cryptography.hazmat.backends

### cryptography.hazmat.primitives.asymmetric.padding

1. **common_imports.py** (Line 110)
   - From module: cryptography.hazmat.primitives.asymmetric
2. **encryption.py** (Line 20)
   - From module: cryptography.hazmat.primitives.asymmetric

### cryptography.hazmat.primitives.asymmetric.rsa

1. **common_imports.py** (Line 110)
   - From module: cryptography.hazmat.primitives.asymmetric
2. **encryption.py** (Line 20)
   - From module: cryptography.hazmat.primitives.asymmetric

### cryptography.hazmat.primitives.ciphers.Cipher

1. **common_imports.py** (Line 107)
   - From module: cryptography.hazmat.primitives.ciphers
2. **encryption.py** (Line 19)
   - From module: cryptography.hazmat.primitives.ciphers

### cryptography.hazmat.primitives.ciphers.algorithms

1. **common_imports.py** (Line 107)
   - From module: cryptography.hazmat.primitives.ciphers
2. **encryption.py** (Line 19)
   - From module: cryptography.hazmat.primitives.ciphers

### cryptography.hazmat.primitives.ciphers.modes

1. **common_imports.py** (Line 107)
   - From module: cryptography.hazmat.primitives.ciphers
2. **encryption.py** (Line 19)
   - From module: cryptography.hazmat.primitives.ciphers

### cryptography.hazmat.primitives.hashes

1. **common_imports.py** (Line 105)
   - From module: cryptography.hazmat.primitives
2. **encryption.py** (Line 17)
   - From module: cryptography.hazmat.primitives

### cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC

1. **common_imports.py** (Line 106)
   - From module: cryptography.hazmat.primitives.kdf.pbkdf2
2. **encryption.py** (Line 18)
   - From module: cryptography.hazmat.primitives.kdf.pbkdf2

### cryptography.hazmat.primitives.serialization

1. **common_imports.py** (Line 109)
   - From module: cryptography.hazmat.primitives
2. **encryption.py** (Line 21)
   - From module: cryptography.hazmat.primitives

### csv

1. **admin.py** (Line 24)
   - From module: csv
2. **admin.py** (Line 640)
   - From module: csv
3. **data_export.py** (Line 7)
   - From module: csv
4. **views.py** (Line 1663)
   - From module: csv
5. **viewset_cap.py** (Line 175)
   - From module: csv
6. **integration_system\data_bridge.py** (Line 376)
   - From module: csv
7. **integration_system\data_bridge.py** (Line 553)
   - From module: csv
8. **integration_system\transformer.py** (Line 265)
   - From module: csv
9. **integration_system\transformer.py** (Line 288)
   - From module: csv
10. **management\commands\export_security_report.py** (Line 15)
   - From module: csv
11. **management\commands\run_security_scan.py** (Line 1051)
   - From module: csv

### dataclasses.dataclass

1. **common_imports.py** (Line 25)
   - From module: dataclasses
2. **endpoint.py** (Line 8)
   - From module: dataclasses
3. **registry.py** (Line 11)
   - From module: dataclasses
4. **resources.py** (Line 8)
   - From module: dataclasses

### dataclasses.field

1. **common_imports.py** (Line 25)
   - From module: dataclasses
2. **endpoint.py** (Line 8)
   - From module: dataclasses
3. **registry.py** (Line 11)
   - From module: dataclasses
4. **resources.py** (Line 8)
   - From module: dataclasses

### datetime

1. **common_imports.py** (Line 18)
   - From module: datetime
2. **serializers.py** (Line 33)
   - From module: datetime

### datetime.datetime

1. **abstracts.py** (Line 9)
   - From module: datetime
2. **admin.py** (Line 5)
   - From module: datetime
3. **analytics.py** (Line 8)
   - From module: datetime
4. **attachment_upload_view.py** (Line 11)
   - From module: datetime
5. **caching.py** (Line 11)
   - From module: datetime
6. **compliance.py** (Line 8)
   - From module: datetime
7. **consumers.py** (Line 10)
   - From module: datetime
8. **data_export.py** (Line 12)
   - From module: datetime
9. **dependencies.py** (Line 12)
   - From module: datetime
10. **duplicate_analyzer.py** (Line 233)
   - From module: datetime
11. **encryption.py** (Line 11)
   - From module: datetime
12. **events.py** (Line 9)
   - From module: datetime
13. **exceptions.py** (Line 9)
   - From module: datetime
14. **factories.py** (Line 8)
   - From module: datetime
15. **factories_backup.py** (Line 8)
   - From module: datetime
16. **feature_flags.py** (Line 8)
   - From module: datetime
17. **filters.py** (Line 12)
   - From module: datetime
18. **fixtures.py** (Line 7)
   - From module: datetime
19. **hash_chain.py** (Line 9)
   - From module: datetime
20. **hooks.py** (Line 8)
   - From module: datetime
21. **interactors.py** (Line 8)
   - From module: datetime
22. **logic.py** (Line 8)
   - From module: datetime
23. **managers.py** (Line 11)
   - From module: datetime
24. **mixins.py** (Line 7)
   - From module: datetime
25. **models.py** (Line 24)
   - From module: datetime
26. **models.py** (Line 7951)
   - From module: datetime
27. **monitoring.py** (Line 10)
   - From module: datetime
28. **notifications_push.py** (Line 9)
   - From module: datetime
29. **openai.py** (Line 12)
   - From module: datetime
30. **plugins.py** (Line 9)
   - From module: datetime
31. **querysets.py** (Line 8)
   - From module: datetime
32. **receivers.py** (Line 7)
   - From module: datetime
33. **repositories.py** (Line 8)
   - From module: datetime
34. **sanctions.py** (Line 8)
   - From module: datetime
35. **schemas.py** (Line 8)
   - From module: datetime
36. **search.py** (Line 9)
   - From module: datetime
37. **selectors.py** (Line 8)
   - From module: datetime
38. **serializers.py** (Line 28)
   - From module: datetime
39. **serializers.py** (Line 8712)
   - From module: datetime
40. **services.py** (Line 14)
   - From module: datetime
41. **signals.py** (Line 13)
   - From module: datetime
42. **signals.py** (Line 448)
   - From module: datetime
43. **signals_cap.py** (Line 9)
   - From module: datetime
44. **signals_kb.py** (Line 8)
   - From module: datetime
45. **tasks.py** (Line 9)
   - From module: datetime
46. **tasks_cap.py** (Line 9)
   - From module: datetime
47. **tests.py** (Line 29)
   - From module: datetime
48. **test_models.py** (Line 10)
   - From module: datetime
49. **test_serializers.py** (Line 10)
   - From module: datetime
50. **test_views.py** (Line 14)
   - From module: datetime
51. **throttling.py** (Line 9)
   - From module: datetime
52. **use_cases.py** (Line 8)
   - From module: datetime
53. **utils.py** (Line 12)
   - From module: datetime
54. **validators.py** (Line 11)
   - From module: datetime
55. **views.py** (Line 8)
   - From module: datetime
56. **webhooks.py** (Line 11)
   - From module: datetime
57. **integration_system\auth_bridge.py** (Line 8)
   - From module: datetime
58. **integration_system\bridge.py** (Line 9)
   - From module: datetime
59. **integration_system\circuit_breaker.py** (Line 9)
   - From module: datetime
60. **integration_system\data_bridge.py** (Line 9)
   - From module: datetime
61. **integration_system\data_validator.py** (Line 9)
   - From module: datetime
62. **integration_system\event_bus.py** (Line 10)
   - From module: datetime
63. **integration_system\fallback_logic.py** (Line 9)
   - From module: datetime
64. **integration_system\health_check.py** (Line 9)
   - From module: datetime
65. **integration_system\integ_adapter.py** (Line 8)
   - From module: datetime
66. **integration_system\integ_audit_logs.py** (Line 9)
   - From module: datetime
67. **integration_system\integ_exceptions.py** (Line 8)
   - From module: datetime
68. **integration_system\integ_handler.py** (Line 9)
   - From module: datetime
69. **integration_system\integ_registry.py** (Line 8)
   - From module: datetime
70. **integration_system\integ_signals.py** (Line 8)
   - From module: datetime
71. **integration_system\message_queue.py** (Line 11)
   - From module: datetime
72. **integration_system\performance_monitor.py** (Line 10)
   - From module: datetime
73. **integration_system\sync_manager.py** (Line 8)
   - From module: datetime
74. **integration_system\transformer.py** (Line 10)
   - From module: datetime
75. **integration_system\versioning.py** (Line 8)
   - From module: datetime
76. **integration_system\webhooks_integration.py** (Line 11)
   - From module: datetime
77. **management\commands\block_suspicious_ips.py** (Line 15)
   - From module: datetime
78. **management\commands\export_security_report.py** (Line 18)
   - From module: datetime
79. **management\commands\run_security_scan.py** (Line 16)
   - From module: datetime
80. **management\commands\seed_security_rules.py** (Line 15)
   - From module: datetime
81. **management\commands\unlock_user_accounts.py** (Line 15)
   - From module: datetime
82. **services\IncidentService.py** (Line 10)
   - From module: datetime
83. **services\PasswordHistoryService.py** (Line 11)
   - From module: datetime
84. **services\SecurityInsightService.py** (Line 11)
   - From module: datetime
85. **services\SecurityPolicyService.py** (Line 11)
   - From module: datetime
86. **services\ThreatIntelService.py** (Line 14)
   - From module: datetime
87. **services\TrustedDeviceService.py** (Line 11)
   - From module: datetime
88. **tests\factories.py** (Line 9)
   - From module: datetime
89. **tests\test_security_models.py** (Line 9)
   - From module: datetime
90. **utils\cache_manager.py** (Line 10)
   - From module: datetime
91. **utils\security_helpers.py** (Line 11)
   - From module: datetime

### datetime.timedelta

1. **abstracts.py** (Line 9)
   - From module: datetime
2. **admin.py** (Line 5)
   - From module: datetime
3. **admin.py** (Line 15)
   - From module: datetime
4. **analytics.py** (Line 8)
   - From module: datetime
5. **caching.py** (Line 11)
   - From module: datetime
6. **celery_beat_config.py** (Line 11)
   - From module: datetime
7. **compliance.py** (Line 8)
   - From module: datetime
8. **constants.py** (Line 8)
   - From module: datetime
9. **context_processors.py** (Line 416)
   - From module: datetime
10. **context_processors.py** (Line 603)
   - From module: datetime
11. **context_processors.py** (Line 626)
   - From module: datetime
12. **data_export.py** (Line 12)
   - From module: datetime
13. **dependencies.py** (Line 12)
   - From module: datetime
14. **encryption.py** (Line 11)
   - From module: datetime
15. **events.py** (Line 9)
   - From module: datetime
16. **factories.py** (Line 8)
   - From module: datetime
17. **factories_backup.py** (Line 8)
   - From module: datetime
18. **feature_flags.py** (Line 8)
   - From module: datetime
19. **filters.py** (Line 12)
   - From module: datetime
20. **fixtures.py** (Line 7)
   - From module: datetime
21. **hooks.py** (Line 8)
   - From module: datetime
22. **interactors.py** (Line 8)
   - From module: datetime
23. **logic.py** (Line 8)
   - From module: datetime
24. **managers.py** (Line 11)
   - From module: datetime
25. **mixins.py** (Line 7)
   - From module: datetime
26. **models.py** (Line 24)
   - From module: datetime
27. **models.py** (Line 48)
   - From module: datetime
28. **models.py** (Line 7951)
   - From module: datetime
29. **monitoring.py** (Line 10)
   - From module: datetime
30. **notifications_push.py** (Line 9)
   - From module: datetime
31. **openai.py** (Line 12)
   - From module: datetime
32. **plugins.py** (Line 9)
   - From module: datetime
33. **querysets.py** (Line 8)
   - From module: datetime
34. **repositories.py** (Line 8)
   - From module: datetime
35. **sanctions.py** (Line 8)
   - From module: datetime
36. **schemas.py** (Line 8)
   - From module: datetime
37. **search.py** (Line 9)
   - From module: datetime
38. **selectors.py** (Line 8)
   - From module: datetime
39. **serializers.py** (Line 28)
   - From module: datetime
40. **serializers.py** (Line 8712)
   - From module: datetime
41. **services.py** (Line 14)
   - From module: datetime
42. **signals_cap.py** (Line 9)
   - From module: datetime
43. **signals_kb.py** (Line 8)
   - From module: datetime
44. **tasks.py** (Line 9)
   - From module: datetime
45. **tasks_cap.py** (Line 9)
   - From module: datetime
46. **tests.py** (Line 10)
   - From module: datetime
47. **tests.py** (Line 29)
   - From module: datetime
48. **test_models.py** (Line 10)
   - From module: datetime
49. **test_serializers.py** (Line 10)
   - From module: datetime
50. **test_views.py** (Line 14)
   - From module: datetime
51. **throttling.py** (Line 9)
   - From module: datetime
52. **use_cases.py** (Line 8)
   - From module: datetime
53. **utils.py** (Line 12)
   - From module: datetime
54. **validators.py** (Line 11)
   - From module: datetime
55. **views.py** (Line 8)
   - From module: datetime
56. **views.py** (Line 9852)
   - From module: datetime
57. **webhooks.py** (Line 11)
   - From module: datetime
58. **integration_system\auth_bridge.py** (Line 8)
   - From module: datetime
59. **integration_system\bridge.py** (Line 9)
   - From module: datetime
60. **integration_system\circuit_breaker.py** (Line 9)
   - From module: datetime
61. **integration_system\data_bridge.py** (Line 9)
   - From module: datetime
62. **integration_system\data_validator.py** (Line 9)
   - From module: datetime
63. **integration_system\event_bus.py** (Line 10)
   - From module: datetime
64. **integration_system\fallback_logic.py** (Line 9)
   - From module: datetime
65. **integration_system\health_check.py** (Line 9)
   - From module: datetime
66. **integration_system\integ_adapter.py** (Line 8)
   - From module: datetime
67. **integration_system\integ_audit_logs.py** (Line 9)
   - From module: datetime
68. **integration_system\integ_exceptions.py** (Line 8)
   - From module: datetime
69. **integration_system\integ_handler.py** (Line 9)
   - From module: datetime
70. **integration_system\integ_registry.py** (Line 8)
   - From module: datetime
71. **integration_system\integ_signals.py** (Line 8)
   - From module: datetime
72. **integration_system\message_queue.py** (Line 11)
   - From module: datetime
73. **integration_system\performance_monitor.py** (Line 10)
   - From module: datetime
74. **integration_system\sync_manager.py** (Line 8)
   - From module: datetime
75. **integration_system\transformer.py** (Line 10)
   - From module: datetime
76. **integration_system\versioning.py** (Line 8)
   - From module: datetime
77. **integration_system\webhooks_integration.py** (Line 11)
   - From module: datetime
78. **management\commands\block_suspicious_ips.py** (Line 15)
   - From module: datetime
79. **management\commands\export_security_report.py** (Line 18)
   - From module: datetime
80. **management\commands\run_security_scan.py** (Line 16)
   - From module: datetime
81. **management\commands\seed_security_rules.py** (Line 15)
   - From module: datetime
82. **management\commands\unlock_user_accounts.py** (Line 15)
   - From module: datetime
83. **services\IncidentService.py** (Line 10)
   - From module: datetime
84. **services\PasswordHistoryService.py** (Line 11)
   - From module: datetime
85. **services\SecurityInsightService.py** (Line 11)
   - From module: datetime
86. **services\SecurityPolicyService.py** (Line 11)
   - From module: datetime
87. **services\ThreatIntelService.py** (Line 14)
   - From module: datetime
88. **services\TrustedDeviceService.py** (Line 11)
   - From module: datetime
89. **tests\factories.py** (Line 9)
   - From module: datetime
90. **tests\test_security_models.py** (Line 9)
   - From module: datetime
91. **utils\cache_manager.py** (Line 10)
   - From module: datetime
92. **utils\device.py** (Line 3)
   - From module: datetime
93. **utils\security_helpers.py** (Line 11)
   - From module: datetime

### decimal.Decimal

1. **models.py** (Line 34)
   - From module: decimal
2. **serializers.py** (Line 34)
   - From module: decimal
3. **serializers.py** (Line 8709)
   - From module: decimal
4. **tests.py** (Line 30)
   - From module: decimal
5. **tests\factories.py** (Line 10)
   - From module: decimal
6. **tests\test_security_models.py** (Line 10)
   - From module: decimal

### decorators.handle_gracefully

1. **views.py** (Line 53)
   - From module: decorators
2. **views.py** (Line 100)
   - From module: decorators

### decorators.method_audit_action

1. **views.py** (Line 47)
   - From module: decorators
2. **views.py** (Line 53)
   - From module: decorators
3. **views.py** (Line 100)
   - From module: decorators

### decorators.rate_limit

1. **endpoint.py** (Line 100)
   - From module: decorators
2. **views.py** (Line 53)
   - From module: decorators
3. **views.py** (Line 100)
   - From module: decorators

### decorators.validate_request

1. **views.py** (Line 53)
   - From module: decorators
2. **views.py** (Line 100)
   - From module: decorators

### django.apps.apps

1. **apps.py** (Line 69)
   - From module: django.apps
2. **hash_chain.py** (Line 452)
   - From module: django.apps
3. **signals.py** (Line 50)
   - From module: django.apps

### django.conf.settings

1. **admin.py** (Line 6634)
   - From module: django.conf
2. **apps.py** (Line 70)
   - From module: django.conf
3. **apps.py** (Line 287)
   - From module: django.conf
4. **attachment_upload_view.py** (Line 12)
   - From module: django.conf
5. **caching.py** (Line 15)
   - From module: django.conf
6. **celery_beat_config.py** (Line 227)
   - From module: django.conf
7. **common_imports.py** (Line 31)
   - From module: django.conf
8. **compliance.py** (Line 13)
   - From module: django.conf
9. **dependencies.py** (Line 13)
   - From module: django.conf
10. **dependencies.py** (Line 610)
   - From module: django.conf
11. **encryption.py** (Line 15)
   - From module: django.conf
12. **events.py** (Line 15)
   - From module: django.conf
13. **feature_flags.py** (Line 13)
   - From module: django.conf
14. **hash_chain.py** (Line 15)
   - From module: django.conf
15. **hooks.py** (Line 13)
   - From module: django.conf
16. **mixins.py** (Line 8)
   - From module: django.conf
17. **models.py** (Line 8)
   - From module: django.conf
18. **models.py** (Line 21)
   - From module: django.conf
19. **monitoring.py** (Line 15)
   - From module: django.conf
20. **notifications_push.py** (Line 14)
   - From module: django.conf
21. **openai.py** (Line 13)
   - From module: django.conf
22. **pagination.py** (Line 14)
   - From module: django.conf
23. **plugins.py** (Line 12)
   - From module: django.conf
24. **registry.py** (Line 8)
   - From module: django.conf
25. **resources.py** (Line 10)
   - From module: django.conf
26. **sanctions.py** (Line 13)
   - From module: django.conf
27. **search.py** (Line 15)
   - From module: django.conf
28. **serializers.py** (Line 23)
   - From module: django.conf
29. **services.py** (Line 18)
   - From module: django.conf
30. **signals.py** (Line 25)
   - From module: django.conf
31. **signals.py** (Line 51)
   - From module: django.conf
32. **signals_cap.py** (Line 15)
   - From module: django.conf
33. **tasks.py** (Line 11)
   - From module: django.conf
34. **tasks.py** (Line 609)
   - From module: django.conf
35. **tasks_cap.py** (Line 14)
   - From module: django.conf
36. **tests.py** (Line 34)
   - From module: django.conf
37. **throttling.py** (Line 11)
   - From module: django.conf
38. **urls_corrected.py** (Line 12)
   - From module: django.conf
39. **utils.py** (Line 14)
   - From module: django.conf
40. **validators.py** (Line 14)
   - From module: django.conf
41. **views.py** (Line 18)
   - From module: django.conf
42. **views.py** (Line 5013)
   - From module: django.conf
43. **views.py** (Line 5736)
   - From module: django.conf
44. **views.py** (Line 6803)
   - From module: django.conf
45. **webhooks.py** (Line 12)
   - From module: django.conf
46. **integration_system\auth_bridge.py** (Line 13)
   - From module: django.conf
47. **integration_system\bridge.py** (Line 14)
   - From module: django.conf
48. **integration_system\circuit_breaker.py** (Line 14)
   - From module: django.conf
49. **integration_system\data_bridge.py** (Line 14)
   - From module: django.conf
50. **integration_system\data_validator.py** (Line 14)
   - From module: django.conf
51. **integration_system\event_bus.py** (Line 15)
   - From module: django.conf
52. **integration_system\fallback_logic.py** (Line 14)
   - From module: django.conf
53. **integration_system\health_check.py** (Line 14)
   - From module: django.conf
54. **integration_system\integ_adapter.py** (Line 13)
   - From module: django.conf
55. **integration_system\integ_audit_logs.py** (Line 14)
   - From module: django.conf
56. **integration_system\integ_handler.py** (Line 14)
   - From module: django.conf
57. **integration_system\integ_registry.py** (Line 13)
   - From module: django.conf
58. **integration_system\integ_signals.py** (Line 14)
   - From module: django.conf
59. **integration_system\message_queue.py** (Line 16)
   - From module: django.conf
60. **integration_system\performance_monitor.py** (Line 15)
   - From module: django.conf
61. **integration_system\sync_manager.py** (Line 13)
   - From module: django.conf
62. **integration_system\transformer.py** (Line 15)
   - From module: django.conf
63. **integration_system\versioning.py** (Line 13)
   - From module: django.conf
64. **integration_system\webhooks_integration.py** (Line 16)
   - From module: django.conf
65. **management\commands\block_suspicious_ips.py** (Line 11)
   - From module: django.conf
66. **management\commands\export_security_report.py** (Line 11)
   - From module: django.conf
67. **management\commands\run_security_scan.py** (Line 11)
   - From module: django.conf
68. **management\commands\seed_security_rules.py** (Line 11)
   - From module: django.conf
69. **management\commands\unlock_user_accounts.py** (Line 11)
   - From module: django.conf
70. **migrations\0002_initial.py** (Line 4)
   - From module: django.conf
71. **migrations\0007_add_missing_security_models.py** (Line 8)
   - From module: django.conf
72. **services\IncidentService.py** (Line 14)
   - From module: django.conf
73. **services\PasswordHistoryService.py** (Line 15)
   - From module: django.conf
74. **services\SecurityInsightService.py** (Line 16)
   - From module: django.conf
75. **services\SecurityPolicyService.py** (Line 15)
   - From module: django.conf
76. **services\ThreatIntelService.py** (Line 18)
   - From module: django.conf
77. **services\TrustedDeviceService.py** (Line 15)
   - From module: django.conf
78. **tests\test_vpn_detector.py** (Line 13)
   - From module: django.conf
79. **utils\device.py** (Line 6)
   - From module: django.conf
80. **utils\security_helpers.py** (Line 13)
   - From module: django.conf

### django.contrib.admin

1. **admin.py** (Line 9)
   - From module: django.contrib
2. **admin.py** (Line 17)
   - From module: django.contrib
3. **admin.py** (Line 6622)
   - From module: django.contrib

### django.contrib.auth.decorators.login_required

1. **admin.py** (Line 21)
   - From module: django.contrib.auth.decorators
2. **admin.py** (Line 6633)
   - From module: django.contrib.auth.decorators
3. **common_imports.py** (Line 65)
   - From module: django.contrib.auth.decorators
4. **serializers.py** (Line 12)
   - From module: django.contrib.auth.decorators

### django.contrib.auth.decorators.permission_required

1. **admin.py** (Line 21)
   - From module: django.contrib.auth.decorators
2. **admin.py** (Line 6633)
   - From module: django.contrib.auth.decorators
3. **common_imports.py** (Line 65)
   - From module: django.contrib.auth.decorators
4. **serializers.py** (Line 12)
   - From module: django.contrib.auth.decorators

### django.contrib.auth.get_user_model

1. **abstracts.py** (Line 11)
   - From module: django.contrib.auth
2. **admin.py** (Line 6628)
   - From module: django.contrib.auth
3. **admin.py** (Line 7250)
   - From module: django.contrib.auth
4. **admin.py** (Line 7349)
   - From module: django.contrib.auth
5. **analytics.py** (Line 10)
   - From module: django.contrib.auth
6. **apps.py** (Line 80)
   - From module: django.contrib.auth
7. **caching.py** (Line 13)
   - From module: django.contrib.auth
8. **common_imports.py** (Line 32)
   - From module: django.contrib.auth
9. **compliance.py** (Line 10)
   - From module: django.contrib.auth
10. **context_processors.py** (Line 9)
   - From module: django.contrib.auth
11. **data_export.py** (Line 14)
   - From module: django.contrib.auth
12. **decorators.py** (Line 13)
   - From module: django.contrib.auth
13. **encryption.py** (Line 13)
   - From module: django.contrib.auth
14. **events.py** (Line 11)
   - From module: django.contrib.auth
15. **factories.py** (Line 19)
   - From module: django.contrib.auth
16. **factories_backup.py** (Line 19)
   - From module: django.contrib.auth
17. **feature_flags.py** (Line 10)
   - From module: django.contrib.auth
18. **fixtures.py** (Line 9)
   - From module: django.contrib.auth
19. **forms.py** (Line 8)
   - From module: django.contrib.auth
20. **hooks.py** (Line 10)
   - From module: django.contrib.auth
21. **interactors.py** (Line 10)
   - From module: django.contrib.auth
22. **logic.py** (Line 10)
   - From module: django.contrib.auth
23. **mixins.py** (Line 9)
   - From module: django.contrib.auth
24. **models.py** (Line 1968)
   - From module: django.contrib.auth
25. **models.py** (Line 8078)
   - From module: django.contrib.auth
26. **monitoring.py** (Line 12)
   - From module: django.contrib.auth
27. **notifications_push.py** (Line 11)
   - From module: django.contrib.auth
28. **plugins.py** (Line 11)
   - From module: django.contrib.auth
29. **querysets.py** (Line 13)
   - From module: django.contrib.auth
30. **receivers.py** (Line 10)
   - From module: django.contrib.auth
31. **repositories.py** (Line 11)
   - From module: django.contrib.auth
32. **resources.py** (Line 13)
   - From module: django.contrib.auth
33. **sanctions.py** (Line 10)
   - From module: django.contrib.auth
34. **schemas.py** (Line 10)
   - From module: django.contrib.auth
35. **search.py** (Line 13)
   - From module: django.contrib.auth
36. **selectors.py** (Line 11)
   - From module: django.contrib.auth
37. **serializers.py** (Line 44)
   - From module: django.contrib.auth
38. **serializers.py** (Line 3424)
   - From module: django.contrib.auth
39. **serializers.py** (Line 4999)
   - From module: django.contrib.auth
40. **services.py** (Line 19)
   - From module: django.contrib.auth
41. **signals_cap.py** (Line 11)
   - From module: django.contrib.auth
42. **signals_kb.py** (Line 12)
   - From module: django.contrib.auth
43. **tasks.py** (Line 12)
   - From module: django.contrib.auth
44. **tasks_cap.py** (Line 11)
   - From module: django.contrib.auth
45. **tests.py** (Line 19)
   - From module: django.contrib.auth
46. **test_models.py** (Line 8)
   - From module: django.contrib.auth
47. **test_serializers.py** (Line 8)
   - From module: django.contrib.auth
48. **test_views.py** (Line 8)
   - From module: django.contrib.auth
49. **throttling.py** (Line 15)
   - From module: django.contrib.auth
50. **use_cases.py** (Line 10)
   - From module: django.contrib.auth
51. **utils.py** (Line 16)
   - From module: django.contrib.auth
52. **validators.py** (Line 15)
   - From module: django.contrib.auth
53. **views.py** (Line 19)
   - From module: django.contrib.auth
54. **views.py** (Line 9853)
   - From module: django.contrib.auth
55. **views.py** (Line 4498)
   - From module: django.contrib.auth
56. **viewset.py** (Line 12)
   - From module: django.contrib.auth
57. **viewset_cap.py** (Line 11)
   - From module: django.contrib.auth
58. **integration_system\auth_bridge.py** (Line 10)
   - From module: django.contrib.auth
59. **integration_system\bridge.py** (Line 11)
   - From module: django.contrib.auth
60. **integration_system\circuit_breaker.py** (Line 11)
   - From module: django.contrib.auth
61. **integration_system\data_bridge.py** (Line 11)
   - From module: django.contrib.auth
62. **integration_system\data_validator.py** (Line 11)
   - From module: django.contrib.auth
63. **integration_system\event_bus.py** (Line 12)
   - From module: django.contrib.auth
64. **integration_system\fallback_logic.py** (Line 11)
   - From module: django.contrib.auth
65. **integration_system\health_check.py** (Line 11)
   - From module: django.contrib.auth
66. **integration_system\integ_adapter.py** (Line 10)
   - From module: django.contrib.auth
67. **integration_system\integ_audit_logs.py** (Line 11)
   - From module: django.contrib.auth
68. **integration_system\integ_handler.py** (Line 11)
   - From module: django.contrib.auth
69. **integration_system\integ_registry.py** (Line 10)
   - From module: django.contrib.auth
70. **integration_system\integ_signals.py** (Line 10)
   - From module: django.contrib.auth
71. **integration_system\message_queue.py** (Line 13)
   - From module: django.contrib.auth
72. **integration_system\performance_monitor.py** (Line 12)
   - From module: django.contrib.auth
73. **integration_system\sync_manager.py** (Line 10)
   - From module: django.contrib.auth
74. **integration_system\transformer.py** (Line 12)
   - From module: django.contrib.auth
75. **integration_system\versioning.py** (Line 10)
   - From module: django.contrib.auth
76. **integration_system\webhooks_integration.py** (Line 13)
   - From module: django.contrib.auth
77. **management\commands\block_suspicious_ips.py** (Line 12)
   - From module: django.contrib.auth
78. **management\commands\export_security_report.py** (Line 12)
   - From module: django.contrib.auth
79. **management\commands\run_security_scan.py** (Line 12)
   - From module: django.contrib.auth
80. **management\commands\seed_security_rules.py** (Line 12)
   - From module: django.contrib.auth
81. **management\commands\unlock_user_accounts.py** (Line 12)
   - From module: django.contrib.auth
82. **services\IncidentService.py** (Line 15)
   - From module: django.contrib.auth
83. **tests\factories.py** (Line 12)
   - From module: django.contrib.auth
84. **tests\test_middleware.py** (Line 11)
   - From module: django.contrib.auth
85. **tests\test_security_models.py** (Line 15)
   - From module: django.contrib.auth
86. **tests\test_security_views.py** (Line 13)
   - From module: django.contrib.auth
87. **utils\device.py** (Line 992)
   - From module: django.contrib.auth

### django.contrib.auth.hashers.make_password

1. **models.py** (Line 18)
   - From module: django.contrib.auth.hashers
2. **management\commands\unlock_user_accounts.py** (Line 424)
   - From module: django.contrib.auth.hashers

### django.contrib.auth.mixins.LoginRequiredMixin

1. **common_imports.py** (Line 64)
   - From module: django.contrib.auth.mixins
2. **serializers.py** (Line 13)
   - From module: django.contrib.auth.mixins

### django.contrib.auth.mixins.PermissionRequiredMixin

1. **common_imports.py** (Line 64)
   - From module: django.contrib.auth.mixins
2. **serializers.py** (Line 13)
   - From module: django.contrib.auth.mixins

### django.contrib.auth.models.Group

1. **common_imports.py** (Line 33)
   - From module: django.contrib.auth.models
2. **permissions.py** (Line 9)
   - From module: django.contrib.auth.models
3. **permissions_backup.py** (Line 9)
   - From module: django.contrib.auth.models

### django.contrib.auth.models.Permission

1. **common_imports.py** (Line 33)
   - From module: django.contrib.auth.models
2. **integration_system\auth_bridge.py** (Line 14)
   - From module: django.contrib.auth.models

### django.contrib.auth.signals.user_logged_in

1. **events.py** (Line 627)
   - From module: django.contrib.auth.signals
2. **receivers.py** (Line 11)
   - From module: django.contrib.auth.signals
3. **signals.py** (Line 19)
   - From module: django.contrib.auth.signals
4. **signals_cap.py** (Line 606)
   - From module: django.contrib.auth.signals
5. **webhooks.py** (Line 506)
   - From module: django.contrib.auth.signals

### django.contrib.auth.signals.user_logged_out

1. **events.py** (Line 627)
   - From module: django.contrib.auth.signals
2. **receivers.py** (Line 11)
   - From module: django.contrib.auth.signals
3. **signals.py** (Line 19)
   - From module: django.contrib.auth.signals
4. **signals_cap.py** (Line 606)
   - From module: django.contrib.auth.signals
5. **webhooks.py** (Line 506)
   - From module: django.contrib.auth.signals

### django.contrib.auth.signals.user_login_failed

1. **events.py** (Line 627)
   - From module: django.contrib.auth.signals
2. **signals.py** (Line 19)
   - From module: django.contrib.auth.signals
3. **signals_cap.py** (Line 606)
   - From module: django.contrib.auth.signals

### django.contrib.auth.views.redirect_to_login

1. **admin.py** (Line 7162)
   - From module: django.contrib.auth.views
2. **mixins.py** (Line 257)
   - From module: django.contrib.auth.views

### django.contrib.contenttypes.models.ContentType

1. **common_imports.py** (Line 67)
   - From module: django.contrib.contenttypes.models
2. **models.py** (Line 5959)
   - From module: django.contrib.contenttypes.models
3. **integration_system\auth_bridge.py** (Line 15)
   - From module: django.contrib.contenttypes.models

### django.contrib.messages

1. **admin.py** (Line 23)
   - From module: django.contrib
2. **common_imports.py** (Line 52)
   - From module: django.contrib
3. **serializers.py** (Line 20)
   - From module: django.contrib

### django.contrib.postgres.fields.ArrayField

1. **common_imports.py** (Line 69)
   - From module: django.contrib.postgres.fields
2. **models.py** (Line 13)
   - From module: django.contrib.postgres.fields

### django.contrib.sessions.models.Session

1. **common_imports.py** (Line 66)
   - From module: django.contrib.sessions.models
2. **signals.py** (Line 478)
   - From module: django.contrib.sessions.models
3. **management\commands\unlock_user_accounts.py** (Line 454)
   - From module: django.contrib.sessions.models

### django.core.cache.cache

1. **analytics.py** (Line 12)
   - From module: django.core.cache
2. **caching.py** (Line 14)
   - From module: django.core.cache
3. **common_imports.py** (Line 34)
   - From module: django.core.cache
4. **compliance.py** (Line 12)
   - From module: django.core.cache
5. **consumers.py** (Line 14)
   - From module: django.core.cache
6. **context_processors.py** (Line 10)
   - From module: django.core.cache
7. **decorators.py** (Line 11)
   - From module: django.core.cache
8. **dependencies.py** (Line 14)
   - From module: django.core.cache
9. **encryption.py** (Line 14)
   - From module: django.core.cache
10. **endpoint.py** (Line 298)
   - From module: django.core.cache
11. **events.py** (Line 13)
   - From module: django.core.cache
12. **feature_flags.py** (Line 12)
   - From module: django.core.cache
13. **hooks.py** (Line 12)
   - From module: django.core.cache
14. **logic.py** (Line 12)
   - From module: django.core.cache
15. **mixins.py** (Line 10)
   - From module: django.core.cache
16. **models.py** (Line 10)
   - From module: django.core.cache
17. **models.py** (Line 25)
   - From module: django.core.cache
18. **models.py** (Line 1247)
   - From module: django.core.cache
19. **monitoring.py** (Line 14)
   - From module: django.core.cache
20. **notifications_push.py** (Line 13)
   - From module: django.core.cache
21. **openai.py** (Line 14)
   - From module: django.core.cache
22. **pagination.py** (Line 12)
   - From module: django.core.cache
23. **permissions.py** (Line 10)
   - From module: django.core.cache
24. **permissions_backup.py** (Line 10)
   - From module: django.core.cache
25. **receivers.py** (Line 12)
   - From module: django.core.cache
26. **registry.py** (Line 9)
   - From module: django.core.cache
27. **repositories.py** (Line 12)
   - From module: django.core.cache
28. **resources.py** (Line 11)
   - From module: django.core.cache
29. **sanctions.py** (Line 12)
   - From module: django.core.cache
30. **search.py** (Line 14)
   - From module: django.core.cache
31. **serializers.py** (Line 18)
   - From module: django.core.cache
32. **services.py** (Line 15)
   - From module: django.core.cache
33. **signals.py** (Line 23)
   - From module: django.core.cache
34. **signals.py** (Line 377)
   - From module: django.core.cache
35. **signals_cap.py** (Line 13)
   - From module: django.core.cache
36. **signals_kb.py** (Line 13)
   - From module: django.core.cache
37. **tasks_cap.py** (Line 13)
   - From module: django.core.cache
38. **tests.py** (Line 17)
   - From module: django.core.cache
39. **throttling.py** (Line 10)
   - From module: django.core.cache
40. **use_cases.py** (Line 12)
   - From module: django.core.cache
41. **utils.py** (Line 15)
   - From module: django.core.cache
42. **views.py** (Line 15)
   - From module: django.core.cache
43. **views.py** (Line 2156)
   - From module: django.core.cache
44. **views.py** (Line 2745)
   - From module: django.core.cache
45. **views.py** (Line 2882)
   - From module: django.core.cache
46. **views.py** (Line 3503)
   - From module: django.core.cache
47. **views.py** (Line 3661)
   - From module: django.core.cache
48. **viewset.py** (Line 15)
   - From module: django.core.cache
49. **viewset_cap.py** (Line 14)
   - From module: django.core.cache
50. **webhooks.py** (Line 15)
   - From module: django.core.cache
51. **integration_system\auth_bridge.py** (Line 12)
   - From module: django.core.cache
52. **integration_system\bridge.py** (Line 13)
   - From module: django.core.cache
53. **integration_system\circuit_breaker.py** (Line 13)
   - From module: django.core.cache
54. **integration_system\data_bridge.py** (Line 13)
   - From module: django.core.cache
55. **integration_system\data_validator.py** (Line 13)
   - From module: django.core.cache
56. **integration_system\event_bus.py** (Line 14)
   - From module: django.core.cache
57. **integration_system\fallback_logic.py** (Line 13)
   - From module: django.core.cache
58. **integration_system\health_check.py** (Line 13)
   - From module: django.core.cache
59. **integration_system\integ_adapter.py** (Line 12)
   - From module: django.core.cache
60. **integration_system\integ_audit_logs.py** (Line 13)
   - From module: django.core.cache
61. **integration_system\integ_handler.py** (Line 13)
   - From module: django.core.cache
62. **integration_system\integ_registry.py** (Line 12)
   - From module: django.core.cache
63. **integration_system\integ_signals.py** (Line 12)
   - From module: django.core.cache
64. **integration_system\message_queue.py** (Line 15)
   - From module: django.core.cache
65. **integration_system\performance_monitor.py** (Line 14)
   - From module: django.core.cache
66. **integration_system\sync_manager.py** (Line 12)
   - From module: django.core.cache
67. **integration_system\transformer.py** (Line 14)
   - From module: django.core.cache
68. **integration_system\versioning.py** (Line 12)
   - From module: django.core.cache
69. **integration_system\webhooks_integration.py** (Line 15)
   - From module: django.core.cache
70. **services\IncidentService.py** (Line 11)
   - From module: django.core.cache
71. **services\PasswordHistoryService.py** (Line 12)
   - From module: django.core.cache
72. **services\SecurityInsightService.py** (Line 12)
   - From module: django.core.cache
73. **services\SecurityPolicyService.py** (Line 12)
   - From module: django.core.cache
74. **services\ThreatIntelService.py** (Line 15)
   - From module: django.core.cache
75. **services\TrustedDeviceService.py** (Line 12)
   - From module: django.core.cache
76. **tests\test_incident_service.py** (Line 11)
   - From module: django.core.cache
77. **tests\test_middleware.py** (Line 12)
   - From module: django.core.cache
78. **tests\test_password_policy.py** (Line 11)
   - From module: django.core.cache
79. **tests\test_security_insight.py** (Line 11)
   - From module: django.core.cache
80. **tests\test_security_policy.py** (Line 11)
   - From module: django.core.cache
81. **tests\test_threat_intel.py** (Line 11)
   - From module: django.core.cache
82. **tests\test_trusted_device.py** (Line 11)
   - From module: django.core.cache
83. **tests\test_vpn_detector.py** (Line 11)
   - From module: django.core.cache
84. **utils\cache_manager.py** (Line 5)
   - From module: django.core.cache
85. **utils\security_helpers.py** (Line 511)
   - From module: django.core.cache

### django.core.exceptions.PermissionDenied

1. **admin.py** (Line 6629)
   - From module: django.core.exceptions
2. **common_imports.py** (Line 35)
   - From module: django.core.exceptions
3. **serializers.py** (Line 19)
   - From module: django.core.exceptions

### django.core.exceptions.ValidationError

1. **common_imports.py** (Line 35)
   - From module: django.core.exceptions
2. **forms.py** (Line 9)
   - From module: django.core.exceptions
3. **models.py** (Line 14)
   - From module: django.core.exceptions
4. **serializers.py** (Line 19)
   - From module: django.core.exceptions
5. **tests.py** (Line 18)
   - From module: django.core.exceptions
6. **validators.py** (Line 13)
   - From module: django.core.exceptions
7. **integration_system\data_validator.py** (Line 15)
   - From module: django.core.exceptions
8. **tests\test_security_models.py** (Line 13)
   - From module: django.core.exceptions

### django.core.mail.get_connection

1. **resources.py** (Line 368)
   - From module: django.core.mail
2. **management\commands\export_security_report.py** (Line 849)
   - From module: django.core.mail

### django.core.mail.mail_admins

1. **tasks.py** (Line 14)
   - From module: django.core.mail
2. **management\commands\block_suspicious_ips.py** (Line 468)
   - From module: django.core.mail

### django.core.mail.send_mail

1. **common_imports.py** (Line 37)
   - From module: django.core.mail
2. **monitoring.py** (Line 698)
   - From module: django.core.mail
3. **notifications_push.py** (Line 583)
   - From module: django.core.mail
4. **resources.py** (Line 359)
   - From module: django.core.mail
5. **tasks.py** (Line 14)
   - From module: django.core.mail
6. **management\commands\unlock_user_accounts.py** (Line 484)
   - From module: django.core.mail

### django.core.management.base.BaseCommand

1. **management\commands\block_suspicious_ips.py** (Line 8)
   - From module: django.core.management.base
2. **management\commands\export_security_report.py** (Line 8)
   - From module: django.core.management.base
3. **management\commands\run_security_scan.py** (Line 8)
   - From module: django.core.management.base
4. **management\commands\seed_security_rules.py** (Line 8)
   - From module: django.core.management.base
5. **management\commands\unlock_user_accounts.py** (Line 8)
   - From module: django.core.management.base

### django.core.management.base.CommandError

1. **management\commands\block_suspicious_ips.py** (Line 8)
   - From module: django.core.management.base
2. **management\commands\export_security_report.py** (Line 8)
   - From module: django.core.management.base
3. **management\commands\run_security_scan.py** (Line 8)
   - From module: django.core.management.base
4. **management\commands\seed_security_rules.py** (Line 8)
   - From module: django.core.management.base
5. **management\commands\unlock_user_accounts.py** (Line 8)
   - From module: django.core.management.base

### django.core.paginator.Paginator

1. **pagination.py** (Line 11)
   - From module: django.core.paginator
2. **serializers.py** (Line 17)
   - From module: django.core.paginator

### django.core.serializers.json.DjangoJSONEncoder

1. **common_imports.py** (Line 39)
   - From module: django.core.serializers.json
2. **data_export.py** (Line 17)
   - From module: django.core.serializers.json

### django.core.validators.MaxValueValidator

1. **common_imports.py** (Line 36)
   - From module: django.core.validators
2. **models.py** (Line 11)
   - From module: django.core.validators

### django.core.validators.MinValueValidator

1. **common_imports.py** (Line 36)
   - From module: django.core.validators
2. **models.py** (Line 11)
   - From module: django.core.validators

### django.core.validators.RegexValidator

1. **common_imports.py** (Line 36)
   - From module: django.core.validators
2. **forms.py** (Line 11)
   - From module: django.core.validators

### django.db.connection

1. **apps.py** (Line 68)
   - From module: django.db
2. **endpoint.py** (Line 289)
   - From module: django.db
3. **monitoring.py** (Line 526)
   - From module: django.db
4. **resources.py** (Line 206)
   - From module: django.db
5. **resources.py** (Line 216)
   - From module: django.db
6. **resources.py** (Line 227)
   - From module: django.db
7. **serializers.py** (Line 25)
   - From module: django.db
8. **tests.py** (Line 20)
   - From module: django.db
9. **tests.py** (Line 1665)
   - From module: django.db
10. **views.py** (Line 2157)
   - From module: django.db
11. **views.py** (Line 2746)
   - From module: django.db
12. **views.py** (Line 2881)
   - From module: django.db
13. **views.py** (Line 3660)
   - From module: django.db

### django.db.connections

1. **integration_system\data_bridge.py** (Line 310)
   - From module: django.db
2. **integration_system\data_bridge.py** (Line 459)
   - From module: django.db
3. **integration_system\health_check.py** (Line 158)
   - From module: django.db

### django.db.migrations

1. **migrations\0001_initial.py** (Line 7)
   - From module: django.db
2. **migrations\0002_initial.py** (Line 5)
   - From module: django.db
3. **migrations\0003_rename_security_ap_version_305516_idx_idx_version_code_is_active_1718_and_more.py** (Line 3)
   - From module: django.db
4. **migrations\0004_rename_idx_version_code_is_active_1718_idx_version_code_is_active_394_and_more.py** (Line 3)
   - From module: django.db
5. **migrations\0005_add_threat_intelligence_and_security_incident.py** (Line 6)
   - From module: django.db
6. **migrations\0006_update_system_integrations.py** (Line 7)
   - From module: django.db
7. **migrations\0007_add_missing_security_models.py** (Line 6)
   - From module: django.db

### django.db.models

1. **abstracts.py** (Line 12)
   - From module: django.db
2. **analytics.py** (Line 11)
   - From module: django.db
3. **caching.py** (Line 16)
   - From module: django.db
4. **common_imports.py** (Line 30)
   - From module: django.db
5. **compliance.py** (Line 11)
   - From module: django.db
6. **feature_flags.py** (Line 11)
   - From module: django.db
7. **hash_chain.py** (Line 11)
   - From module: django.db
8. **managers.py** (Line 8)
   - From module: django.db
9. **mixins.py** (Line 11)
   - From module: django.db
10. **models.py** (Line 7)
   - From module: django.db
11. **models.py** (Line 20)
   - From module: django.db
12. **models.py** (Line 44)
   - From module: django.db
13. **model_mixins.py** (Line 6)
   - From module: django.db
14. **monitoring.py** (Line 13)
   - From module: django.db
15. **notifications_push.py** (Line 12)
   - From module: django.db
16. **querysets.py** (Line 9)
   - From module: django.db
17. **repositories.py** (Line 9)
   - From module: django.db
18. **sanctions.py** (Line 11)
   - From module: django.db
19. **search.py** (Line 10)
   - From module: django.db
20. **selectors.py** (Line 9)
   - From module: django.db
21. **signals_kb.py** (Line 14)
   - From module: django.db
22. **tasks.py** (Line 796)
   - From module: django.db
23. **webhooks.py** (Line 14)
   - From module: django.db
24. **management\commands\block_suspicious_ips.py** (Line 587)
   - From module: django.db
25. **management\commands\run_security_scan.py** (Line 1095)
   - From module: django.db
26. **migrations\0001_initial.py** (Line 7)
   - From module: django.db
27. **migrations\0002_initial.py** (Line 5)
   - From module: django.db
28. **migrations\0005_add_threat_intelligence_and_security_incident.py** (Line 6)
   - From module: django.db
29. **migrations\0006_update_system_integrations.py** (Line 7)
   - From module: django.db
30. **migrations\0007_add_missing_security_models.py** (Line 6)
   - From module: django.db
31. **services\ThreatIntelService.py** (Line 17)
   - From module: django.db

### django.db.models.Avg

1. **admin.py** (Line 13)
   - From module: django.db.models
2. **analytics.py** (Line 13)
   - From module: django.db.models
3. **common_imports.py** (Line 54)
   - From module: django.db.models
4. **managers.py** (Line 9)
   - From module: django.db.models
5. **models.py** (Line 12)
   - From module: django.db.models
6. **querysets.py** (Line 10)
   - From module: django.db.models
7. **search.py** (Line 11)
   - From module: django.db.models
8. **serializers.py** (Line 15)
   - From module: django.db.models
9. **views.py** (Line 22)
   - From module: django.db.models
10. **views.py** (Line 8636)
   - From module: django.db.models
11. **viewset.py** (Line 14)
   - From module: django.db.models
12. **management\commands\export_security_report.py** (Line 886)
   - From module: django.db.models
13. **services\SecurityInsightService.py** (Line 15)
   - From module: django.db.models

### django.db.models.Count

1. **admin.py** (Line 13)
   - From module: django.db.models
2. **admin.py** (Line 6626)
   - From module: django.db.models
3. **admin.py** (Line 3047)
   - From module: django.db.models
4. **analytics.py** (Line 13)
   - From module: django.db.models
5. **common_imports.py** (Line 54)
   - From module: django.db.models
6. **managers.py** (Line 9)
   - From module: django.db.models
7. **models.py** (Line 12)
   - From module: django.db.models
8. **models.py** (Line 45)
   - From module: django.db.models
9. **models.py** (Line 7950)
   - From module: django.db.models
10. **notifications_push.py** (Line 414)
   - From module: django.db.models
11. **querysets.py** (Line 10)
   - From module: django.db.models
12. **search.py** (Line 11)
   - From module: django.db.models
13. **serializers.py** (Line 15)
   - From module: django.db.models
14. **views.py** (Line 22)
   - From module: django.db.models
15. **views.py** (Line 32)
   - From module: django.db.models
16. **views.py** (Line 9850)
   - From module: django.db.models
17. **views.py** (Line 8636)
   - From module: django.db.models
18. **viewset.py** (Line 14)
   - From module: django.db.models
19. **management\commands\export_security_report.py** (Line 886)
   - From module: django.db.models
20. **services\SecurityInsightService.py** (Line 15)
   - From module: django.db.models

### django.db.models.F

1. **analytics.py** (Line 13)
   - From module: django.db.models
2. **common_imports.py** (Line 54)
   - From module: django.db.models
3. **models.py** (Line 12)
   - From module: django.db.models
4. **querysets.py** (Line 10)
   - From module: django.db.models
5. **serializers.py** (Line 15)
   - From module: django.db.models
6. **views.py** (Line 22)
   - From module: django.db.models
7. **views.py** (Line 32)
   - From module: django.db.models

### django.db.models.Func

1. **analytics.py** (Line 13)
   - From module: django.db.models
2. **common_imports.py** (Line 54)
   - From module: django.db.models
3. **querysets.py** (Line 10)
   - From module: django.db.models

### django.db.models.Max

1. **analytics.py** (Line 13)
   - From module: django.db.models
2. **common_imports.py** (Line 54)
   - From module: django.db.models
3. **managers.py** (Line 9)
   - From module: django.db.models
4. **querysets.py** (Line 10)
   - From module: django.db.models
5. **search.py** (Line 11)
   - From module: django.db.models
6. **views.py** (Line 22)
   - From module: django.db.models
7. **viewset.py** (Line 14)
   - From module: django.db.models
8. **management\commands\export_security_report.py** (Line 886)
   - From module: django.db.models

### django.db.models.Min

1. **analytics.py** (Line 13)
   - From module: django.db.models
2. **common_imports.py** (Line 54)
   - From module: django.db.models
3. **managers.py** (Line 9)
   - From module: django.db.models
4. **querysets.py** (Line 10)
   - From module: django.db.models
5. **search.py** (Line 11)
   - From module: django.db.models
6. **views.py** (Line 22)
   - From module: django.db.models
7. **viewset.py** (Line 14)
   - From module: django.db.models

### django.db.models.Q

1. **admin.py** (Line 13)
   - From module: django.db.models
2. **analytics.py** (Line 13)
   - From module: django.db.models
3. **common_imports.py** (Line 54)
   - From module: django.db.models
4. **filters.py** (Line 10)
   - From module: django.db.models
5. **managers.py** (Line 9)
   - From module: django.db.models
6. **models.py** (Line 12)
   - From module: django.db.models
7. **models.py** (Line 26)
   - From module: django.db.models
8. **models.py** (Line 45)
   - From module: django.db.models
9. **pagination.py** (Line 342)
   - From module: django.db.models
10. **querysets.py** (Line 10)
   - From module: django.db.models
11. **receivers.py** (Line 14)
   - From module: django.db.models
12. **search.py** (Line 11)
   - From module: django.db.models
13. **serializers.py** (Line 15)
   - From module: django.db.models
14. **views.py** (Line 22)
   - From module: django.db.models
15. **views.py** (Line 32)
   - From module: django.db.models
16. **viewset.py** (Line 14)
   - From module: django.db.models
17. **viewset_cap.py** (Line 13)
   - From module: django.db.models
18. **services\SecurityInsightService.py** (Line 15)
   - From module: django.db.models

### django.db.models.QuerySet

1. **admin.py** (Line 6626)
   - From module: django.db.models
2. **data_export.py** (Line 16)
   - From module: django.db.models

### django.db.models.Sum

1. **admin.py** (Line 13)
   - From module: django.db.models
2. **analytics.py** (Line 13)
   - From module: django.db.models
3. **common_imports.py** (Line 54)
   - From module: django.db.models
4. **managers.py** (Line 9)
   - From module: django.db.models
5. **models.py** (Line 12)
   - From module: django.db.models
6. **models.py** (Line 7950)
   - From module: django.db.models
7. **querysets.py** (Line 10)
   - From module: django.db.models
8. **search.py** (Line 11)
   - From module: django.db.models
9. **serializers.py** (Line 15)
   - From module: django.db.models
10. **views.py** (Line 2059)
   - From module: django.db.models
11. **views.py** (Line 2084)
   - From module: django.db.models
12. **viewset.py** (Line 14)
   - From module: django.db.models
13. **services\SecurityInsightService.py** (Line 15)
   - From module: django.db.models

### django.db.models.Value

1. **analytics.py** (Line 13)
   - From module: django.db.models
2. **querysets.py** (Line 10)
   - From module: django.db.models

### django.db.models.Window

1. **common_imports.py** (Line 54)
   - From module: django.db.models
2. **serializers.py** (Line 15)
   - From module: django.db.models
3. **views.py** (Line 22)
   - From module: django.db.models

### django.db.models.deletion

1. **migrations\0002_initial.py** (Line 3)
   - From module: django.db.models.deletion
2. **migrations\0005_add_threat_intelligence_and_security_incident.py** (Line 7)
   - From module: django.db.models.deletion
3. **migrations\0006_update_system_integrations.py** (Line 8)
   - From module: django.db.models.deletion
4. **migrations\0007_add_missing_security_models.py** (Line 7)
   - From module: django.db.models.deletion

### django.db.models.functions.Cast

1. **analytics.py** (Line 14)
   - From module: django.db.models.functions
2. **common_imports.py** (Line 55)
   - From module: django.db.models.functions

### django.db.models.functions.Coalesce

1. **common_imports.py** (Line 55)
   - From module: django.db.models.functions
2. **querysets.py** (Line 11)
   - From module: django.db.models.functions
3. **views.py** (Line 23)
   - From module: django.db.models.functions

### django.db.models.functions.Extract

1. **analytics.py** (Line 14)
   - From module: django.db.models.functions
2. **common_imports.py** (Line 55)
   - From module: django.db.models.functions

### django.db.models.functions.Trunc

1. **analytics.py** (Line 14)
   - From module: django.db.models.functions
2. **common_imports.py** (Line 55)
   - From module: django.db.models.functions

### django.db.models.functions.TruncDay

1. **views.py** (Line 23)
   - From module: django.db.models.functions
2. **views.py** (Line 33)
   - From module: django.db.models.functions
3. **views.py** (Line 6670)
   - From module: django.db.models.functions
4. **views.py** (Line 7669)
   - From module: django.db.models.functions

### django.db.models.functions.TruncHour

1. **serializers.py** (Line 16)
   - From module: django.db.models.functions
2. **views.py** (Line 23)
   - From module: django.db.models.functions
3. **views.py** (Line 33)
   - From module: django.db.models.functions

### django.db.models.signals.m2m_changed

1. **common_imports.py** (Line 56)
   - From module: django.db.models.signals
2. **signals.py** (Line 14)
   - From module: django.db.models.signals

### django.db.models.signals.post_delete

1. **common_imports.py** (Line 56)
   - From module: django.db.models.signals
2. **models.py** (Line 15)
   - From module: django.db.models.signals
3. **receivers.py** (Line 8)
   - From module: django.db.models.signals
4. **signals.py** (Line 14)
   - From module: django.db.models.signals
5. **signals_cap.py** (Line 613)
   - From module: django.db.models.signals
6. **signals_kb.py** (Line 9)
   - From module: django.db.models.signals

### django.db.models.signals.post_save

1. **common_imports.py** (Line 56)
   - From module: django.db.models.signals
2. **hash_chain.py** (Line 12)
   - From module: django.db.models.signals
3. **models.py** (Line 15)
   - From module: django.db.models.signals
4. **models.py** (Line 46)
   - From module: django.db.models.signals
5. **receivers.py** (Line 8)
   - From module: django.db.models.signals
6. **serializers.py** (Line 3222)
   - From module: django.db.models.signals
7. **signals.py** (Line 14)
   - From module: django.db.models.signals
8. **signals_cap.py** (Line 613)
   - From module: django.db.models.signals
9. **signals_kb.py** (Line 9)
   - From module: django.db.models.signals
10. **webhooks.py** (Line 505)
   - From module: django.db.models.signals

### django.db.models.signals.pre_delete

1. **common_imports.py** (Line 56)
   - From module: django.db.models.signals
2. **signals.py** (Line 14)
   - From module: django.db.models.signals

### django.db.models.signals.pre_save

1. **common_imports.py** (Line 56)
   - From module: django.db.models.signals
2. **hash_chain.py** (Line 12)
   - From module: django.db.models.signals
3. **models.py** (Line 19)
   - From module: django.db.models.signals
4. **models.py** (Line 46)
   - From module: django.db.models.signals
5. **receivers.py** (Line 8)
   - From module: django.db.models.signals
6. **signals.py** (Line 14)
   - From module: django.db.models.signals
7. **signals_kb.py** (Line 9)
   - From module: django.db.models.signals

### django.db.transaction

1. **common_imports.py** (Line 30)
   - From module: django.db
2. **decorators.py** (Line 10)
   - From module: django.db
3. **events.py** (Line 12)
   - From module: django.db
4. **hooks.py** (Line 11)
   - From module: django.db
5. **interactors.py** (Line 11)
   - From module: django.db
6. **logic.py** (Line 11)
   - From module: django.db
7. **models.py** (Line 44)
   - From module: django.db
8. **repositories.py** (Line 9)
   - From module: django.db
9. **sanctions.py** (Line 11)
   - From module: django.db
10. **serializers.py** (Line 25)
   - From module: django.db
11. **serializers.py** (Line 8707)
   - From module: django.db
12. **services.py** (Line 17)
   - From module: django.db
13. **signals_cap.py** (Line 12)
   - From module: django.db
14. **tasks.py** (Line 13)
   - From module: django.db
15. **tasks_cap.py** (Line 12)
   - From module: django.db
16. **tests.py** (Line 20)
   - From module: django.db
17. **tests.py** (Line 33)
   - From module: django.db
18. **use_cases.py** (Line 11)
   - From module: django.db
19. **views.py** (Line 21)
   - From module: django.db
20. **integration_system\auth_bridge.py** (Line 11)
   - From module: django.db
21. **integration_system\bridge.py** (Line 12)
   - From module: django.db
22. **integration_system\circuit_breaker.py** (Line 12)
   - From module: django.db
23. **integration_system\data_bridge.py** (Line 12)
   - From module: django.db
24. **integration_system\data_validator.py** (Line 12)
   - From module: django.db
25. **integration_system\event_bus.py** (Line 13)
   - From module: django.db
26. **integration_system\fallback_logic.py** (Line 12)
   - From module: django.db
27. **integration_system\health_check.py** (Line 12)
   - From module: django.db
28. **integration_system\integ_adapter.py** (Line 11)
   - From module: django.db
29. **integration_system\integ_audit_logs.py** (Line 12)
   - From module: django.db
30. **integration_system\integ_handler.py** (Line 12)
   - From module: django.db
31. **integration_system\integ_registry.py** (Line 11)
   - From module: django.db
32. **integration_system\integ_signals.py** (Line 11)
   - From module: django.db
33. **integration_system\message_queue.py** (Line 14)
   - From module: django.db
34. **integration_system\performance_monitor.py** (Line 13)
   - From module: django.db
35. **integration_system\sync_manager.py** (Line 11)
   - From module: django.db
36. **integration_system\transformer.py** (Line 13)
   - From module: django.db
37. **integration_system\versioning.py** (Line 11)
   - From module: django.db
38. **integration_system\webhooks_integration.py** (Line 14)
   - From module: django.db
39. **management\commands\block_suspicious_ips.py** (Line 10)
   - From module: django.db
40. **management\commands\export_security_report.py** (Line 10)
   - From module: django.db
41. **management\commands\run_security_scan.py** (Line 10)
   - From module: django.db
42. **management\commands\seed_security_rules.py** (Line 10)
   - From module: django.db
43. **management\commands\unlock_user_accounts.py** (Line 10)
   - From module: django.db
44. **services\IncidentService.py** (Line 13)
   - From module: django.db
45. **services\PasswordHistoryService.py** (Line 14)
   - From module: django.db
46. **services\SecurityInsightService.py** (Line 14)
   - From module: django.db
47. **services\SecurityPolicyService.py** (Line 14)
   - From module: django.db
48. **services\ThreatIntelService.py** (Line 17)
   - From module: django.db
49. **services\TrustedDeviceService.py** (Line 14)
   - From module: django.db
50. **tests\test_incident_service.py** (Line 13)
   - From module: django.db
51. **tests\test_password_policy.py** (Line 13)
   - From module: django.db
52. **tests\test_security_insight.py** (Line 13)
   - From module: django.db
53. **tests\test_security_models.py** (Line 14)
   - From module: django.db
54. **tests\test_security_policy.py** (Line 13)
   - From module: django.db
55. **tests\test_threat_intel.py** (Line 13)
   - From module: django.db
56. **tests\test_trusted_device.py** (Line 13)
   - From module: django.db

### django.dispatch.Signal

1. **common_imports.py** (Line 57)
   - From module: django.dispatch
2. **events.py** (Line 14)
   - From module: django.dispatch
3. **monitoring.py** (Line 16)
   - From module: django.dispatch
4. **signals_cap.py** (Line 14)
   - From module: django.dispatch
5. **signals_kb.py** (Line 10)
   - From module: django.dispatch
6. **integration_system\integ_signals.py** (Line 13)
   - From module: django.dispatch

### django.dispatch.receiver

1. **common_imports.py** (Line 57)
   - From module: django.dispatch
2. **hash_chain.py** (Line 13)
   - From module: django.dispatch
3. **models.py** (Line 16)
   - From module: django.dispatch
4. **receivers.py** (Line 9)
   - From module: django.dispatch
5. **signals.py** (Line 18)
   - From module: django.dispatch
6. **signals_cap.py** (Line 14)
   - From module: django.dispatch
7. **signals_kb.py** (Line 10)
   - From module: django.dispatch
8. **integration_system\integ_signals.py** (Line 13)
   - From module: django.dispatch

### django.http.HttpRequest

1. **admin.py** (Line 22)
   - From module: django.http
2. **admin.py** (Line 6627)
   - From module: django.http
3. **integration_system\webhooks_integration.py** (Line 17)
   - From module: django.http
4. **utils\device.py** (Line 7)
   - From module: django.http

### django.http.HttpResponse

1. **admin.py** (Line 22)
   - From module: django.http
2. **admin.py** (Line 6627)
   - From module: django.http
3. **admin.py** (Line 641)
   - From module: django.http
4. **attachment_upload_view.py** (Line 13)
   - From module: django.http
5. **common_imports.py** (Line 47)
   - From module: django.http
6. **data_export.py** (Line 15)
   - From module: django.http
7. **decorators.py** (Line 12)
   - From module: django.http
8. **endpoint.py** (Line 13)
   - From module: django.http
9. **feature_flags.py** (Line 724)
   - From module: django.http
10. **serializers.py** (Line 8)
   - From module: django.http
11. **tests.py** (Line 2055)
   - From module: django.http
12. **throttling.py** (Line 16)
   - From module: django.http
13. **views.py** (Line 1664)
   - From module: django.http
14. **viewset_cap.py** (Line 176)
   - From module: django.http
15. **viewset_cap.py** (Line 205)
   - From module: django.http
16. **viewset_cap.py** (Line 225)
   - From module: django.http
17. **webhooks.py** (Line 17)
   - From module: django.http
18. **integration_system\webhooks_integration.py** (Line 17)
   - From module: django.http
19. **tests\test_middleware.py** (Line 14)
   - From module: django.http

### django.http.JsonResponse

1. **admin.py** (Line 6627)
   - From module: django.http
2. **attachment_upload_view.py** (Line 13)
   - From module: django.http
3. **common_imports.py** (Line 47)
   - From module: django.http
4. **decorators.py** (Line 12)
   - From module: django.http
5. **endpoint.py** (Line 13)
   - From module: django.http
6. **mixins.py** (Line 12)
   - From module: django.http
7. **serializers.py** (Line 8)
   - From module: django.http
8. **utils\device.py** (Line 867)
   - From module: django.http

### django.shortcuts.get_object_or_404

1. **common_imports.py** (Line 48)
   - From module: django.shortcuts
2. **serializers.py** (Line 7)
   - From module: django.shortcuts

### django.shortcuts.render

1. **admin.py** (Line 6624)
   - From module: django.shortcuts
2. **common_imports.py** (Line 48)
   - From module: django.shortcuts
3. **mixins.py** (Line 353)
   - From module: django.shortcuts
4. **mixins.py** (Line 417)
   - From module: django.shortcuts
5. **serializers.py** (Line 7)
   - From module: django.shortcuts
6. **views.py** (Line 50)
   - From module: django.shortcuts

### django.test.RequestFactory

1. **tests.py** (Line 2060)
   - From module: django.test
2. **tests\test_middleware.py** (Line 10)
   - From module: django.test

### django.test.TestCase

1. **tests.py** (Line 14)
   - From module: django.test
2. **tests.py** (Line 32)
   - From module: django.test
3. **test_models.py** (Line 7)
   - From module: django.test
4. **test_serializers.py** (Line 7)
   - From module: django.test
5. **test_views.py** (Line 7)
   - From module: django.test
6. **tests\test_incident_service.py** (Line 10)
   - From module: django.test
7. **tests\test_middleware.py** (Line 10)
   - From module: django.test
8. **tests\test_password_policy.py** (Line 10)
   - From module: django.test
9. **tests\test_security_insight.py** (Line 10)
   - From module: django.test
10. **tests\test_security_models.py** (Line 11)
   - From module: django.test
11. **tests\test_security_policy.py** (Line 10)
   - From module: django.test
12. **tests\test_security_views.py** (Line 10)
   - From module: django.test
13. **tests\test_threat_intel.py** (Line 10)
   - From module: django.test
14. **tests\test_trusted_device.py** (Line 10)
   - From module: django.test
15. **tests\test_vpn_detector.py** (Line 10)
   - From module: django.test

### django.test.TransactionTestCase

1. **tests.py** (Line 32)
   - From module: django.test
2. **tests\test_security_models.py** (Line 11)
   - From module: django.test
3. **tests\test_security_views.py** (Line 10)
   - From module: django.test

### django.test.override_settings

1. **tests.py** (Line 14)
   - From module: django.test
2. **tests\test_middleware.py** (Line 10)
   - From module: django.test

### django.urls.include

1. **endpoint.py** (Line 10)
   - From module: django.urls
2. **urls_corrected.py** (Line 10)
   - From module: django.urls

### django.urls.path

1. **admin.py** (Line 12)
   - From module: django.urls
2. **admin.py** (Line 6623)
   - From module: django.urls
3. **endpoint.py** (Line 10)
   - From module: django.urls
4. **urls_corrected.py** (Line 10)
   - From module: django.urls

### django.urls.re_path

1. **endpoint.py** (Line 10)
   - From module: django.urls
2. **routing.py** (Line 6)
   - From module: django.urls
3. **urls_corrected.py** (Line 13)
   - From module: django.urls

### django.urls.reverse

1. **admin.py** (Line 11)
   - From module: django.urls
2. **admin.py** (Line 6623)
   - From module: django.urls
3. **common_imports.py** (Line 46)
   - From module: django.urls
4. **tests.py** (Line 15)
   - From module: django.urls
5. **test_views.py** (Line 10)
   - From module: django.urls
6. **webhooks.py** (Line 16)
   - From module: django.urls
7. **tests\test_security_views.py** (Line 11)
   - From module: django.urls

### django.utils.decorators.method_decorator

1. **attachment_upload_view.py** (Line 18)
   - From module: django.utils.decorators
2. **decorators.py** (Line 9)
   - From module: django.utils.decorators
3. **endpoint.py** (Line 12)
   - From module: django.utils.decorators
4. **serializers.py** (Line 14)
   - From module: django.utils.decorators
5. **views.py** (Line 25)
   - From module: django.utils.decorators
6. **integration_system\webhooks_integration.py** (Line 20)
   - From module: django.utils.decorators

### django.utils.safestring.mark_safe

1. **admin.py** (Line 68)
   - From module: django.utils.safestring
2. **admin.py** (Line 80)
   - From module: django.utils.safestring

### django.utils.timezone

1. **abstracts.py** (Line 10)
   - From module: django.utils
2. **admin.py** (Line 14)
   - From module: django.utils
3. **admin.py** (Line 6625)
   - From module: django.utils
4. **analytics.py** (Line 9)
   - From module: django.utils
5. **caching.py** (Line 12)
   - From module: django.utils
6. **common_imports.py** (Line 40)
   - From module: django.utils
7. **compliance.py** (Line 9)
   - From module: django.utils
8. **consumers.py** (Line 15)
   - From module: django.utils
9. **context_processors.py** (Line 8)
   - From module: django.utils
10. **data_export.py** (Line 13)
   - From module: django.utils
11. **decorators.py** (Line 14)
   - From module: django.utils
12. **dependencies.py** (Line 15)
   - From module: django.utils
13. **encryption.py** (Line 12)
   - From module: django.utils
14. **events.py** (Line 10)
   - From module: django.utils
15. **exceptions.py** (Line 10)
   - From module: django.utils
16. **factories.py** (Line 9)
   - From module: django.utils
17. **factories_backup.py** (Line 9)
   - From module: django.utils
18. **feature_flags.py** (Line 9)
   - From module: django.utils
19. **filters.py** (Line 11)
   - From module: django.utils
20. **fixtures.py** (Line 8)
   - From module: django.utils
21. **forms.py** (Line 10)
   - From module: django.utils
22. **hash_chain.py** (Line 14)
   - From module: django.utils
23. **hooks.py** (Line 9)
   - From module: django.utils
24. **interactors.py** (Line 9)
   - From module: django.utils
25. **logic.py** (Line 9)
   - From module: django.utils
26. **managers.py** (Line 10)
   - From module: django.utils
27. **mixins.py** (Line 13)
   - From module: django.utils
28. **models.py** (Line 9)
   - From module: django.utils
29. **models.py** (Line 22)
   - From module: django.utils
30. **model_mixins.py** (Line 7)
   - From module: django.utils
31. **monitoring.py** (Line 11)
   - From module: django.utils
32. **notifications_push.py** (Line 10)
   - From module: django.utils
33. **openai.py** (Line 15)
   - From module: django.utils
34. **pagination.py** (Line 13)
   - From module: django.utils
35. **permissions.py** (Line 11)
   - From module: django.utils
36. **permissions_backup.py** (Line 11)
   - From module: django.utils
37. **permissions_backup.py** (Line 508)
   - From module: django.utils
38. **plugins.py** (Line 10)
   - From module: django.utils
39. **querysets.py** (Line 12)
   - From module: django.utils
40. **receivers.py** (Line 13)
   - From module: django.utils
41. **repositories.py** (Line 10)
   - From module: django.utils
42. **resources.py** (Line 12)
   - From module: django.utils
43. **sanctions.py** (Line 9)
   - From module: django.utils
44. **schemas.py** (Line 9)
   - From module: django.utils
45. **search.py** (Line 12)
   - From module: django.utils
46. **selectors.py** (Line 10)
   - From module: django.utils
47. **serializers.py** (Line 22)
   - From module: django.utils
48. **serializers.py** (Line 8706)
   - From module: django.utils
49. **serializers.py** (Line 11858)
   - From module: django.utils
50. **services.py** (Line 16)
   - From module: django.utils
51. **signals.py** (Line 24)
   - From module: django.utils
52. **signals_cap.py** (Line 10)
   - From module: django.utils
53. **signals_kb.py** (Line 11)
   - From module: django.utils
54. **tasks.py** (Line 10)
   - From module: django.utils
55. **tasks_cap.py** (Line 10)
   - From module: django.utils
56. **tests.py** (Line 16)
   - From module: django.utils
57. **test_models.py** (Line 9)
   - From module: django.utils
58. **test_serializers.py** (Line 9)
   - From module: django.utils
59. **test_views.py** (Line 9)
   - From module: django.utils
60. **throttling.py** (Line 12)
   - From module: django.utils
61. **use_cases.py** (Line 9)
   - From module: django.utils
62. **utils.py** (Line 17)
   - From module: django.utils
63. **validators.py** (Line 12)
   - From module: django.utils
64. **views.py** (Line 24)
   - From module: django.utils
65. **viewset.py** (Line 13)
   - From module: django.utils
66. **viewset_cap.py** (Line 12)
   - From module: django.utils
67. **webhooks.py** (Line 13)
   - From module: django.utils
68. **integration_system\auth_bridge.py** (Line 9)
   - From module: django.utils
69. **integration_system\bridge.py** (Line 10)
   - From module: django.utils
70. **integration_system\circuit_breaker.py** (Line 10)
   - From module: django.utils
71. **integration_system\data_bridge.py** (Line 10)
   - From module: django.utils
72. **integration_system\data_validator.py** (Line 10)
   - From module: django.utils
73. **integration_system\event_bus.py** (Line 11)
   - From module: django.utils
74. **integration_system\fallback_logic.py** (Line 10)
   - From module: django.utils
75. **integration_system\health_check.py** (Line 10)
   - From module: django.utils
76. **integration_system\integ_adapter.py** (Line 9)
   - From module: django.utils
77. **integration_system\integ_audit_logs.py** (Line 10)
   - From module: django.utils
78. **integration_system\integ_exceptions.py** (Line 9)
   - From module: django.utils
79. **integration_system\integ_handler.py** (Line 10)
   - From module: django.utils
80. **integration_system\integ_registry.py** (Line 9)
   - From module: django.utils
81. **integration_system\integ_signals.py** (Line 9)
   - From module: django.utils
82. **integration_system\message_queue.py** (Line 12)
   - From module: django.utils
83. **integration_system\performance_monitor.py** (Line 11)
   - From module: django.utils
84. **integration_system\sync_manager.py** (Line 9)
   - From module: django.utils
85. **integration_system\transformer.py** (Line 11)
   - From module: django.utils
86. **integration_system\versioning.py** (Line 9)
   - From module: django.utils
87. **integration_system\webhooks_integration.py** (Line 12)
   - From module: django.utils
88. **management\commands\block_suspicious_ips.py** (Line 9)
   - From module: django.utils
89. **management\commands\export_security_report.py** (Line 9)
   - From module: django.utils
90. **management\commands\run_security_scan.py** (Line 9)
   - From module: django.utils
91. **management\commands\seed_security_rules.py** (Line 9)
   - From module: django.utils
92. **management\commands\unlock_user_accounts.py** (Line 9)
   - From module: django.utils
93. **migrations\0001_initial.py** (Line 5)
   - From module: django.utils.timezone
94. **migrations\0005_add_threat_intelligence_and_security_incident.py** (Line 8)
   - From module: django.utils.timezone
95. **services\IncidentService.py** (Line 12)
   - From module: django.utils
96. **services\PasswordHistoryService.py** (Line 13)
   - From module: django.utils
97. **services\SecurityInsightService.py** (Line 13)
   - From module: django.utils
98. **services\SecurityPolicyService.py** (Line 13)
   - From module: django.utils
99. **services\ThreatIntelService.py** (Line 16)
   - From module: django.utils
100. **services\TrustedDeviceService.py** (Line 13)
   - From module: django.utils
101. **tests\factories.py** (Line 11)
   - From module: django.utils
102. **tests\test_incident_service.py** (Line 12)
   - From module: django.utils
103. **tests\test_middleware.py** (Line 13)
   - From module: django.utils
104. **tests\test_password_policy.py** (Line 12)
   - From module: django.utils
105. **tests\test_security_insight.py** (Line 12)
   - From module: django.utils
106. **tests\test_security_models.py** (Line 12)
   - From module: django.utils
107. **tests\test_security_policy.py** (Line 12)
   - From module: django.utils
108. **tests\test_security_views.py** (Line 12)
   - From module: django.utils
109. **tests\test_threat_intel.py** (Line 12)
   - From module: django.utils
110. **tests\test_trusted_device.py** (Line 12)
   - From module: django.utils
111. **tests\test_vpn_detector.py** (Line 12)
   - From module: django.utils
112. **utils\device.py** (Line 5)
   - From module: django.utils
113. **utils\security_helpers.py** (Line 12)
   - From module: django.utils

### django.utils.translation._

1. **common_imports.py** (Line 41)
   - From module: django.utils.translation
2. **models.py** (Line 17)
   - From module: django.utils.translation

### django.views.View

1. **attachment_upload_view.py** (Line 19)
   - From module: django.views
2. **endpoint.py** (Line 14)
   - From module: django.views
3. **serializers.py** (Line 9)
   - From module: django.views

### django.views.decorators.cache.cache_page

1. **common_imports.py** (Line 51)
   - From module: django.views.decorators.cache
2. **views.py** (Line 26)
   - From module: django.views.decorators.cache

### django.views.decorators.cache.never_cache

1. **admin.py** (Line 19)
   - From module: django.views.decorators.cache
2. **admin.py** (Line 6631)
   - From module: django.views.decorators.cache
3. **common_imports.py** (Line 51)
   - From module: django.views.decorators.cache

### django.views.decorators.csrf.csrf_exempt

1. **attachment_upload_view.py** (Line 14)
   - From module: django.views.decorators.csrf
2. **common_imports.py** (Line 50)
   - From module: django.views.decorators.csrf
3. **endpoint.py** (Line 11)
   - From module: django.views.decorators.csrf
4. **mixins.py** (Line 14)
   - From module: django.views.decorators.csrf
5. **serializers.py** (Line 11)
   - From module: django.views.decorators.csrf
6. **integration_system\webhooks_integration.py** (Line 18)
   - From module: django.views.decorators.csrf

### django.views.decorators.csrf.csrf_protect

1. **admin.py** (Line 20)
   - From module: django.views.decorators.csrf
2. **admin.py** (Line 6632)
   - From module: django.views.decorators.csrf
3. **common_imports.py** (Line 50)
   - From module: django.views.decorators.csrf

### django.views.decorators.http.require_http_methods

1. **attachment_upload_view.py** (Line 15)
   - From module: django.views.decorators.http
2. **common_imports.py** (Line 49)
   - From module: django.views.decorators.http
3. **serializers.py** (Line 10)
   - From module: django.views.decorators.http
4. **integration_system\webhooks_integration.py** (Line 19)
   - From module: django.views.decorators.http

### django_filters.BooleanFilter

1. **filters.py** (Line 9)
   - From module: django_filters
2. **views.py** (Line 46)
   - From module: django_filters

### django_filters.CharFilter

1. **filters.py** (Line 9)
   - From module: django_filters
2. **views.py** (Line 46)
   - From module: django_filters

### django_filters.ChoiceFilter

1. **filters.py** (Line 9)
   - From module: django_filters
2. **views.py** (Line 46)
   - From module: django_filters

### django_filters.DateTimeFilter

1. **filters.py** (Line 9)
   - From module: django_filters
2. **views.py** (Line 46)
   - From module: django_filters

### django_filters.FilterSet

1. **filters.py** (Line 9)
   - From module: django_filters
2. **views.py** (Line 46)
   - From module: django_filters

### django_filters.NumberFilter

1. **filters.py** (Line 9)
   - From module: django_filters
2. **views.py** (Line 46)
   - From module: django_filters

### django_filters.rest_framework.DjangoFilterBackend

1. **views.py** (Line 48)
   - From module: django_filters.rest_framework
2. **viewset.py** (Line 16)
   - From module: django_filters.rest_framework

### email.mime.multipart.MIMEMultipart

1. **common_imports.py** (Line 127)
   - From module: email.mime.multipart
2. **dependencies.py** (Line 556)
   - From module: email.mime.multipart

### email.mime.text.MIMEText

1. **common_imports.py** (Line 126)
   - From module: email.mime.text
2. **dependencies.py** (Line 555)
   - From module: email.mime.text

### enum.Enum

1. **choices.py** (Line 7)
   - From module: enum
2. **common_imports.py** (Line 26)
   - From module: enum
3. **endpoint.py** (Line 9)
   - From module: enum
4. **exceptions.py** (Line 12)
   - From module: enum
5. **registry.py** (Line 12)
   - From module: enum
6. **resources.py** (Line 9)
   - From module: enum

### factories.DeviceInfoFactory

1. **tests\test_security_models.py** (Line 19)
   - From module: factories
2. **tests\test_security_views.py** (Line 24)
   - From module: factories
3. **tests\test_trusted_device.py** (Line 17)
   - From module: factories

### factories.IPBlacklistFactory

1. **tests\test_security_insight.py** (Line 17)
   - From module: factories
2. **tests\test_security_models.py** (Line 19)
   - From module: factories
3. **tests\test_threat_intel.py** (Line 17)
   - From module: factories
4. **tests\test_vpn_detector.py** (Line 19)
   - From module: factories
5. **tests\test_vpn_detector.py** (Line 416)
   - From module: factories

### factories.PasswordHistoryFactory

1. **tests\test_password_policy.py** (Line 17)
   - From module: factories
2. **tests\test_security_models.py** (Line 19)
   - From module: factories
3. **tests\test_security_views.py** (Line 24)
   - From module: factories

### factories.RiskScoreFactory

1. **tests\test_security_models.py** (Line 19)
   - From module: factories
2. **tests\test_security_views.py** (Line 24)
   - From module: factories

### factories.SecurityIncidentFactory

1. **tests\test_incident_service.py** (Line 17)
   - From module: factories
2. **tests\test_security_models.py** (Line 19)
   - From module: factories
3. **tests\test_security_views.py** (Line 24)
   - From module: factories
4. **tests\test_threat_intel.py** (Line 17)
   - From module: factories

### factories.SecurityInsightFactory

1. **tests\test_security_insight.py** (Line 17)
   - From module: factories
2. **tests\test_security_models.py** (Line 19)
   - From module: factories
3. **tests\test_security_views.py** (Line 24)
   - From module: factories

### factories.SecurityLogFactory

1. **tests\test_incident_service.py** (Line 17)
   - From module: factories
2. **tests\test_middleware.py** (Line 21)
   - From module: factories
3. **tests\test_password_policy.py** (Line 17)
   - From module: factories
4. **tests\test_security_insight.py** (Line 17)
   - From module: factories
5. **tests\test_security_models.py** (Line 19)
   - From module: factories
6. **tests\test_security_policy.py** (Line 17)
   - From module: factories
7. **tests\test_security_views.py** (Line 24)
   - From module: factories
8. **tests\test_threat_intel.py** (Line 17)
   - From module: factories
9. **tests\test_trusted_device.py** (Line 17)
   - From module: factories

### factories.SecurityPolicyFactory

1. **tests\test_password_policy.py** (Line 17)
   - From module: factories
2. **tests\test_security_models.py** (Line 19)
   - From module: factories
3. **tests\test_security_policy.py** (Line 17)
   - From module: factories
4. **tests\test_security_views.py** (Line 24)
   - From module: factories

### factories.StaffUserFactory

1. **tests\test_incident_service.py** (Line 17)
   - From module: factories
2. **tests\test_middleware.py** (Line 21)
   - From module: factories
3. **tests\test_password_policy.py** (Line 17)
   - From module: factories
4. **tests\test_security_insight.py** (Line 17)
   - From module: factories
5. **tests\test_security_models.py** (Line 19)
   - From module: factories
6. **tests\test_security_policy.py** (Line 17)
   - From module: factories
7. **tests\test_security_views.py** (Line 24)
   - From module: factories
8. **tests\test_threat_intel.py** (Line 17)
   - From module: factories
9. **tests\test_trusted_device.py** (Line 17)
   - From module: factories

### factories.SuperUserFactory

1. **tests\test_security_models.py** (Line 19)
   - From module: factories
2. **tests\test_security_views.py** (Line 24)
   - From module: factories

### factories.ThreatIntelligenceFactory

1. **tests\test_incident_service.py** (Line 17)
   - From module: factories
2. **tests\test_security_models.py** (Line 19)
   - From module: factories
3. **tests\test_security_views.py** (Line 24)
   - From module: factories
4. **tests\test_threat_intel.py** (Line 17)
   - From module: factories
5. **tests\test_vpn_detector.py** (Line 19)
   - From module: factories
6. **tests\test_vpn_detector.py** (Line 416)
   - From module: factories

### factories.TrustedDeviceFactory

1. **tests\test_security_models.py** (Line 19)
   - From module: factories
2. **tests\test_security_views.py** (Line 24)
   - From module: factories
3. **tests\test_trusted_device.py** (Line 17)
   - From module: factories

### factories.UserBanFactory

1. **tests\test_incident_service.py** (Line 17)
   - From module: factories
2. **tests\test_security_insight.py** (Line 17)
   - From module: factories
3. **tests\test_security_models.py** (Line 19)
   - From module: factories
4. **tests\test_security_policy.py** (Line 17)
   - From module: factories
5. **tests\test_security_views.py** (Line 24)
   - From module: factories

### factories.UserFactory

1. **tests\test_incident_service.py** (Line 17)
   - From module: factories
2. **tests\test_middleware.py** (Line 21)
   - From module: factories
3. **tests\test_password_policy.py** (Line 17)
   - From module: factories
4. **tests\test_security_insight.py** (Line 17)
   - From module: factories
5. **tests\test_security_models.py** (Line 19)
   - From module: factories
6. **tests\test_security_policy.py** (Line 17)
   - From module: factories
7. **tests\test_security_views.py** (Line 24)
   - From module: factories
8. **tests\test_threat_intel.py** (Line 17)
   - From module: factories
9. **tests\test_trusted_device.py** (Line 17)
   - From module: factories
10. **tests\test_vpn_detector.py** (Line 19)
   - From module: factories

### factory.Factory

1. **common_imports.py** (Line 116)
   - From module: factory
2. **factories.py** (Line 10)
   - From module: factory
3. **factories_backup.py** (Line 10)
   - From module: factory
4. **tests\factories.py** (Line 13)
   - From module: factory

### factory.LazyAttribute

1. **common_imports.py** (Line 116)
   - From module: factory
2. **tests\factories.py** (Line 13)
   - From module: factory

### factory.Sequence

1. **common_imports.py** (Line 116)
   - From module: factory
2. **tests\factories.py** (Line 13)
   - From module: factory

### factory.django

1. **common_imports.py** (Line 116)
   - From module: factory
2. **factories.py** (Line 10)
   - From module: factory
3. **factories_backup.py** (Line 10)
   - From module: factory

### factory.fuzzy

1. **common_imports.py** (Line 116)
   - From module: factory
2. **factories.py** (Line 10)
   - From module: factory
3. **factories_backup.py** (Line 10)
   - From module: factory

### factory.post_generation

1. **common_imports.py** (Line 116)
   - From module: factory
2. **factories.py** (Line 10)
   - From module: factory
3. **factories_backup.py** (Line 10)
   - From module: factory

### faker.Faker

1. **common_imports.py** (Line 115)
   - From module: faker
2. **factories.py** (Line 11)
   - From module: faker
3. **factories_backup.py** (Line 11)
   - From module: faker
4. **tests\factories.py** (Line 15)
   - From module: faker

### functools

1. **decorators.py** (Line 18)
   - From module: functools
2. **permissions.py** (Line 14)
   - From module: functools
3. **permissions_backup.py** (Line 14)
   - From module: functools
4. **views.py** (Line 49)
   - From module: functools
5. **utils\cache_manager.py** (Line 8)
   - From module: functools
6. **utils\device.py** (Line 9)
   - From module: functools

### functools.wraps

1. **admin.py** (Line 7)
   - From module: functools
2. **admin.py** (Line 18)
   - From module: functools
3. **common_imports.py** (Line 23)
   - From module: functools
4. **decorators.py** (Line 8)
   - From module: functools
5. **serializers.py** (Line 36)
   - From module: functools
6. **views.py** (Line 16)
   - From module: functools

### hash_chain.HashChainedModel

1. **common_imports.py** (Line 159)
   - From module: hash_chain
2. **models.py** (Line 51)
   - From module: hash_chain
3. **receivers.py** (Line 21)
   - From module: hash_chain

### hashlib

1. **attachment_upload_view.py** (Line 10)
   - From module: hashlib
2. **caching.py** (Line 7)
   - From module: hashlib
3. **common_imports.py** (Line 7)
   - From module: hashlib
4. **decorators.py** (Line 20)
   - From module: hashlib
5. **dependencies.py** (Line 17)
   - From module: hashlib
6. **hash_chain.py** (Line 6)
   - From module: hashlib
7. **models.py** (Line 28)
   - From module: hashlib
8. **openai.py** (Line 18)
   - From module: hashlib
9. **plugins.py** (Line 570)
   - From module: hashlib
10. **plugins.py** (Line 616)
   - From module: hashlib
11. **serializers.py** (Line 37)
   - From module: hashlib
12. **serializers.py** (Line 1656)
   - From module: hashlib
13. **signals.py** (Line 360)
   - From module: hashlib
14. **tests.py** (Line 160)
   - From module: hashlib
15. **tests.py** (Line 388)
   - From module: hashlib
16. **utils.py** (Line 6)
   - From module: hashlib
17. **validators.py** (Line 9)
   - From module: hashlib
18. **views.py** (Line 11)
   - From module: hashlib
19. **webhooks.py** (Line 7)
   - From module: hashlib
20. **integration_system\webhooks_integration.py** (Line 7)
   - From module: hashlib
21. **services\ThreatIntelService.py** (Line 12)
   - From module: hashlib
22. **utils\cache_manager.py** (Line 11)
   - From module: hashlib
23. **utils\security_helpers.py** (Line 8)
   - From module: hashlib

### helpers.SecurityMetrics

1. **analytics.py** (Line 19)
   - From module: helpers
2. **events.py** (Line 19)
   - From module: helpers
3. **hooks.py** (Line 17)
   - From module: helpers
4. **interactors.py** (Line 23)
   - From module: helpers
5. **logic.py** (Line 16)
   - From module: helpers
6. **monitoring.py** (Line 20)
   - From module: helpers
7. **signals_cap.py** (Line 19)
   - From module: helpers
8. **signals_kb.py** (Line 18)
   - From module: helpers
9. **tasks_cap.py** (Line 21)
   - From module: helpers
10. **use_cases.py** (Line 20)
   - From module: helpers

### helpers.TimeHelper

1. **analytics.py** (Line 19)
   - From module: helpers
2. **compliance.py** (Line 17)
   - From module: helpers
3. **data_export.py** (Line 22)
   - From module: helpers
4. **events.py** (Line 19)
   - From module: helpers
5. **hooks.py** (Line 17)
   - From module: helpers
6. **logic.py** (Line 16)
   - From module: helpers
7. **sanctions.py** (Line 18)
   - From module: helpers
8. **search.py** (Line 18)
   - From module: helpers
9. **signals_cap.py** (Line 19)
   - From module: helpers
10. **tasks_cap.py** (Line 21)
   - From module: helpers

### hmac

1. **common_imports.py** (Line 16)
   - From module: hmac
2. **dependencies.py** (Line 18)
   - From module: hmac
3. **models.py** (Line 38)
   - From module: hmac
4. **webhooks.py** (Line 8)
   - From module: hmac
5. **integration_system\webhooks_integration.py** (Line 8)
   - From module: hmac

### integ_adapter.adapter_registry

1. **integration_system\bridge.py** (Line 19)
   - From module: integ_adapter
2. **integration_system\integ_registry.py** (Line 18)
   - From module: integ_adapter

### integ_constants.*

1. **integration_system\bridge.py** (Line 20)
   - From module: integ_constants
2. **integration_system\data_bridge.py** (Line 19)
   - From module: integ_constants
3. **integration_system\event_bus.py** (Line 19)
   - From module: integ_constants
4. **integration_system\transformer.py** (Line 19)
   - From module: integ_constants
5. **integration_system\versioning.py** (Line 17)
   - From module: integ_constants
6. **integration_system\webhooks_integration.py** (Line 28)
   - From module: integ_constants

### integ_handler.BaseIntegrationHandler

1. **integration_system\data_bridge.py** (Line 18)
   - From module: integ_handler
2. **integration_system\integ_adapter.py** (Line 17)
   - From module: integ_handler
3. **integration_system\integ_registry.py** (Line 17)
   - From module: integ_handler
4. **integration_system\webhooks_integration.py** (Line 27)
   - From module: integ_handler

### integ_handler.integration_handler

1. **integration_system\bridge.py** (Line 18)
   - From module: integ_handler
2. **integration_system\health_check.py** (Line 437)
   - From module: integ_handler
3. **integration_system\integ_registry.py** (Line 17)
   - From module: integ_handler
4. **integration_system\integ_signals.py** (Line 18)
   - From module: integ_handler

### io

1. **data_export.py** (Line 9)
   - From module: io
2. **integration_system\transformer.py** (Line 266)
   - From module: io
3. **integration_system\transformer.py** (Line 289)
   - From module: io
4. **management\commands\export_security_report.py** (Line 17)
   - From module: io
5. **management\commands\export_security_report.py** (Line 792)
   - From module: io

### io.StringIO

1. **viewset_cap.py** (Line 177)
   - From module: io
2. **management\commands\run_security_scan.py** (Line 1052)
   - From module: io

### ipaddress

1. **common_imports.py** (Line 14)
   - From module: ipaddress
2. **filters.py** (Line 222)
   - From module: ipaddress
3. **filters.py** (Line 721)
   - From module: ipaddress
4. **forms.py** (Line 175)
   - From module: ipaddress
5. **logic.py** (Line 571)
   - From module: ipaddress
6. **mixins.py** (Line 382)
   - From module: ipaddress
7. **models.py** (Line 33)
   - From module: ipaddress
8. **models.py** (Line 6981)
   - From module: ipaddress
9. **models.py** (Line 7871)
   - From module: ipaddress
10. **models.py** (Line 6864)
   - From module: ipaddress
11. **model_mixins.py** (Line 247)
   - From module: ipaddress
12. **model_mixins.py** (Line 256)
   - From module: ipaddress
13. **serializers.py** (Line 3171)
   - From module: ipaddress
14. **serializers.py** (Line 420)
   - From module: ipaddress
15. **serializers.py** (Line 3621)
   - From module: ipaddress
16. **serializers.py** (Line 3837)
   - From module: ipaddress
17. **serializers.py** (Line 3398)
   - From module: ipaddress
18. **utils.py** (Line 9)
   - From module: ipaddress
19. **validators.py** (Line 10)
   - From module: ipaddress
20. **utils\security_helpers.py** (Line 466)
   - From module: ipaddress

### json

1. **admin.py** (Line 16)
   - From module: json
2. **caching.py** (Line 9)
   - From module: json
3. **common_imports.py** (Line 9)
   - From module: json
4. **consumers.py** (Line 8)
   - From module: json
5. **data_export.py** (Line 8)
   - From module: json
6. **decorators.py** (Line 19)
   - From module: json
7. **decorators.py** (Line 1205)
   - From module: json
8. **dependencies.py** (Line 10)
   - From module: json
9. **fixtures.py** (Line 6)
   - From module: json
10. **forms.py** (Line 60)
   - From module: json
11. **hash_chain.py** (Line 7)
   - From module: json
12. **managers.py** (Line 14)
   - From module: json
13. **models.py** (Line 30)
   - From module: json
14. **notifications_push.py** (Line 7)
   - From module: json
15. **openai.py** (Line 9)
   - From module: json
16. **pagination.py** (Line 221)
   - From module: json
17. **pagination.py** (Line 247)
   - From module: json
18. **serializers.py** (Line 3640)
   - From module: json
19. **services.py** (Line 12)
   - From module: json
20. **tasks.py** (Line 16)
   - From module: json
21. **tests.py** (Line 8)
   - From module: json
22. **tests.py** (Line 27)
   - From module: json
23. **utils.py** (Line 20)
   - From module: json
24. **views.py** (Line 14)
   - From module: json
25. **viewset_cap.py** (Line 206)
   - From module: json
26. **webhooks.py** (Line 9)
   - From module: json
27. **integration_system\data_bridge.py** (Line 375)
   - From module: json
28. **integration_system\data_bridge.py** (Line 552)
   - From module: json
29. **integration_system\event_bus.py** (Line 8)
   - From module: json
30. **integration_system\integ_adapter.py** (Line 446)
   - From module: json
31. **integration_system\integ_adapter.py** (Line 473)
   - From module: json
32. **integration_system\integ_audit_logs.py** (Line 7)
   - From module: json
33. **integration_system\message_queue.py** (Line 8)
   - From module: json
34. **integration_system\transformer.py** (Line 7)
   - From module: json
35. **integration_system\webhooks_integration.py** (Line 9)
   - From module: json
36. **management\commands\block_suspicious_ips.py** (Line 14)
   - From module: json
37. **management\commands\export_security_report.py** (Line 14)
   - From module: json
38. **management\commands\run_security_scan.py** (Line 14)
   - From module: json
39. **management\commands\seed_security_rules.py** (Line 14)
   - From module: json
40. **management\commands\unlock_user_accounts.py** (Line 14)
   - From module: json
41. **services\IncidentService.py** (Line 8)
   - From module: json
42. **services\ThreatIntelService.py** (Line 11)
   - From module: json
43. **tests\test_incident_service.py** (Line 8)
   - From module: json
44. **tests\test_middleware.py** (Line 8)
   - From module: json
45. **tests\test_password_policy.py** (Line 8)
   - From module: json
46. **tests\test_security_insight.py** (Line 8)
   - From module: json
47. **tests\test_security_policy.py** (Line 8)
   - From module: json
48. **tests\test_security_views.py** (Line 8)
   - From module: json
49. **tests\test_threat_intel.py** (Line 8)
   - From module: json
50. **tests\test_trusted_device.py** (Line 8)
   - From module: json
51. **tests\test_vpn_detector.py** (Line 8)
   - From module: json
52. **utils\cache_manager.py** (Line 12)
   - From module: json

### logging

1. **abstracts.py** (Line 6)
   - From module: logging
2. **admin.py** (Line 6)
   - From module: logging
3. **analytics.py** (Line 6)
   - From module: logging
4. **apps.py** (Line 9)
   - From module: logging
5. **attachment_upload_view.py** (Line 24)
   - From module: logging
6. **caching.py** (Line 6)
   - From module: logging
7. **common_imports.py** (Line 8)
   - From module: logging
8. **compliance.py** (Line 6)
   - From module: logging
9. **consumers.py** (Line 9)
   - From module: logging
10. **context_processors.py** (Line 6)
   - From module: logging
11. **data_export.py** (Line 6)
   - From module: logging
12. **decorators.py** (Line 16)
   - From module: logging
13. **dependencies.py** (Line 8)
   - From module: logging
14. **encryption.py** (Line 6)
   - From module: logging
15. **endpoint.py** (Line 6)
   - From module: logging
16. **events.py** (Line 6)
   - From module: logging
17. **exceptions.py** (Line 8)
   - From module: logging
18. **feature_flags.py** (Line 6)
   - From module: logging
19. **forms.py** (Line 6)
   - From module: logging
20. **hash_chain.py** (Line 8)
   - From module: logging
21. **hooks.py** (Line 6)
   - From module: logging
22. **interactors.py** (Line 6)
   - From module: logging
23. **logic.py** (Line 6)
   - From module: logging
24. **managers.py** (Line 13)
   - From module: logging
25. **mixins.py** (Line 6)
   - From module: logging
26. **models.py** (Line 29)
   - From module: logging
27. **monitoring.py** (Line 6)
   - From module: logging
28. **notifications_push.py** (Line 6)
   - From module: logging
29. **openai.py** (Line 8)
   - From module: logging
30. **pagination.py** (Line 6)
   - From module: logging
31. **permissions.py** (Line 13)
   - From module: logging
32. **permissions_backup.py** (Line 13)
   - From module: logging
33. **plugins.py** (Line 6)
   - From module: logging
34. **querysets.py** (Line 6)
   - From module: logging
35. **receivers.py** (Line 6)
   - From module: logging
36. **registry.py** (Line 6)
   - From module: logging
37. **repositories.py** (Line 6)
   - From module: logging
38. **resources.py** (Line 6)
   - From module: logging
39. **sanctions.py** (Line 6)
   - From module: logging
40. **schemas.py** (Line 6)
   - From module: logging
41. **search.py** (Line 6)
   - From module: logging
42. **selectors.py** (Line 6)
   - From module: logging
43. **serializers.py** (Line 32)
   - From module: logging
44. **serializers.py** (Line 8710)
   - From module: logging
45. **services.py** (Line 11)
   - From module: logging
46. **signals.py** (Line 11)
   - From module: logging
47. **signals_cap.py** (Line 6)
   - From module: logging
48. **signals_kb.py** (Line 6)
   - From module: logging
49. **tasks.py** (Line 8)
   - From module: logging
50. **tasks_cap.py** (Line 6)
   - From module: logging
51. **tests.py** (Line 7)
   - From module: logging
52. **throttling.py** (Line 6)
   - From module: logging
53. **use_cases.py** (Line 6)
   - From module: logging
54. **utils.py** (Line 11)
   - From module: logging
55. **validators.py** (Line 17)
   - From module: logging
56. **views.py** (Line 7)
   - From module: logging
57. **viewset.py** (Line 6)
   - From module: logging
58. **viewset_cap.py** (Line 6)
   - From module: logging
59. **webhooks.py** (Line 6)
   - From module: logging
60. **integration_system\auth_bridge.py** (Line 6)
   - From module: logging
61. **integration_system\bridge.py** (Line 6)
   - From module: logging
62. **integration_system\circuit_breaker.py** (Line 6)
   - From module: logging
63. **integration_system\data_bridge.py** (Line 6)
   - From module: logging
64. **integration_system\data_validator.py** (Line 6)
   - From module: logging
65. **integration_system\event_bus.py** (Line 6)
   - From module: logging
66. **integration_system\fallback_logic.py** (Line 6)
   - From module: logging
67. **integration_system\health_check.py** (Line 6)
   - From module: logging
68. **integration_system\integ_adapter.py** (Line 6)
   - From module: logging
69. **integration_system\integ_audit_logs.py** (Line 6)
   - From module: logging
70. **integration_system\integ_exceptions.py** (Line 6)
   - From module: logging
71. **integration_system\integ_handler.py** (Line 6)
   - From module: logging
72. **integration_system\integ_registry.py** (Line 6)
   - From module: logging
73. **integration_system\integ_signals.py** (Line 6)
   - From module: logging
74. **integration_system\message_queue.py** (Line 6)
   - From module: logging
75. **integration_system\performance_monitor.py** (Line 6)
   - From module: logging
76. **integration_system\sync_manager.py** (Line 6)
   - From module: logging
77. **integration_system\transformer.py** (Line 6)
   - From module: logging
78. **integration_system\versioning.py** (Line 6)
   - From module: logging
79. **integration_system\webhooks_integration.py** (Line 6)
   - From module: logging
80. **management\commands\block_suspicious_ips.py** (Line 13)
   - From module: logging
81. **management\commands\export_security_report.py** (Line 13)
   - From module: logging
82. **management\commands\run_security_scan.py** (Line 13)
   - From module: logging
83. **management\commands\seed_security_rules.py** (Line 13)
   - From module: logging
84. **management\commands\unlock_user_accounts.py** (Line 13)
   - From module: logging
85. **services\IncidentService.py** (Line 7)
   - From module: logging
86. **services\PasswordHistoryService.py** (Line 9)
   - From module: logging
87. **services\SecurityInsightService.py** (Line 9)
   - From module: logging
88. **services\SecurityPolicyService.py** (Line 9)
   - From module: logging
89. **services\ThreatIntelService.py** (Line 10)
   - From module: logging
90. **services\TrustedDeviceService.py** (Line 9)
   - From module: logging
91. **utils\cache_manager.py** (Line 7)
   - From module: logging
92. **utils\device.py** (Line 2)
   - From module: logging
93. **utils\security_helpers.py** (Line 7)
   - From module: logging
94. **utils\__init__.py** (Line 9)
   - From module: logging

### logic.security_logic_engine

1. **context_processors.py** (Line 244)
   - From module: logic
2. **tasks_cap.py** (Line 135)
   - From module: logic

### mixins.RateLimitMixin

1. **viewset.py** (Line 19)
   - From module: mixins
2. **viewset_cap.py** (Line 17)
   - From module: mixins

### mixins.SecurityAuditMixin

1. **viewset.py** (Line 19)
   - From module: mixins
2. **viewset_cap.py** (Line 17)
   - From module: mixins

### mixins.SecurityHeadersMixin

1. **viewset.py** (Line 19)
   - From module: mixins
2. **viewset_cap.py** (Line 17)
   - From module: mixins

### models.APIRateLimit

1. **apps.py** (Line 81)
   - From module: models
2. **serializers.py** (Line 58)
   - From module: models
3. **services.py** (Line 25)
   - From module: models
4. **signals.py** (Line 31)
   - From module: models
5. **views.py** (Line 61)
   - From module: models
6. **views.py** (Line 3958)
   - From module: models

### models.AlertRule

1. **serializers.py** (Line 58)
   - From module: models
2. **views.py** (Line 61)
   - From module: models

### models.AppVersion

1. **decorators.py** (Line 22)
   - From module: models
2. **serializers.py** (Line 58)
   - From module: models
3. **views.py** (Line 61)
   - From module: models

### models.AuditLog

1. **decorators.py** (Line 714)
   - From module: models
2. **decorators.py** (Line 845)
   - From module: models

### models.AuditTrail

1. **common_imports.py** (Line 142)
   - From module: models
2. **factories.py** (Line 13)
   - From module: models
3. **factories_backup.py** (Line 13)
   - From module: models
4. **fixtures.py** (Line 10)
   - From module: models
5. **receivers.py** (Line 17)
   - From module: models
6. **serializers.py** (Line 58)
   - From module: models
7. **test_models.py** (Line 13)
   - From module: models
8. **views.py** (Line 61)
   - From module: models

### models.AutoBlockRule

1. **serializers.py** (Line 58)
   - From module: models
2. **views.py** (Line 61)
   - From module: models
3. **views.py** (Line 3539)
   - From module: models

### models.ClickTracker

1. **serializers.py** (Line 58)
   - From module: models
2. **services.py** (Line 25)
   - From module: models
3. **signals.py** (Line 31)
   - From module: models
4. **views.py** (Line 61)
   - From module: models
5. **views.py** (Line 61)
   - From module: models

### models.Country

1. **serializers.py** (Line 58)
   - From module: models
2. **services.py** (Line 25)
   - From module: models
3. **signals.py** (Line 31)
   - From module: models
4. **views.py** (Line 61)
   - From module: models

### models.CountryBlockRule

1. **filters.py** (Line 15)
   - From module: models
2. **serializers.py** (Line 58)
   - From module: models
3. **services.py** (Line 25)
   - From module: models
4. **signals.py** (Line 31)
   - From module: models
5. **validators.py** (Line 315)
   - From module: models
6. **views.py** (Line 61)
   - From module: models

### models.DataExport

1. **serializers.py** (Line 58)
   - From module: models
2. **views.py** (Line 61)
   - From module: models

### models.DataImport

1. **serializers.py** (Line 58)
   - From module: models
2. **views.py** (Line 61)
   - From module: models

### models.DeviceInfo

1. **admin.py** (Line 6641)
   - From module: models
2. **admin.py** (Line 7284)
   - From module: models
3. **admin.py** (Line 7368)
   - From module: models
4. **analytics.py** (Line 16)
   - From module: models
5. **apps.py** (Line 81)
   - From module: models
6. **caching.py** (Line 438)
   - From module: models
7. **common_imports.py** (Line 142)
   - From module: models
8. **context_processors.py** (Line 294)
   - From module: models
9. **context_processors.py** (Line 476)
   - From module: models
10. **context_processors.py** (Line 572)
   - From module: models
11. **data_export.py** (Line 19)
   - From module: models
12. **factories.py** (Line 13)
   - From module: models
13. **factories_backup.py** (Line 13)
   - From module: models
14. **filters.py** (Line 15)
   - From module: models
15. **fixtures.py** (Line 10)
   - From module: models
16. **logic.py** (Line 14)
   - From module: models
17. **permissions.py** (Line 20)
   - From module: models
18. **permissions_backup.py** (Line 20)
   - From module: models
19. **receivers.py** (Line 17)
   - From module: models
20. **repositories.py** (Line 14)
   - From module: models
21. **selectors.py** (Line 203)
   - From module: models
22. **serializers.py** (Line 31)
   - From module: models
23. **serializers.py** (Line 58)
   - From module: models
24. **services.py** (Line 25)
   - From module: models
25. **signals.py** (Line 31)
   - From module: models
26. **tasks_cap.py** (Line 139)
   - From module: models
27. **test_models.py** (Line 13)
   - From module: models
28. **test_serializers.py** (Line 15)
   - From module: models
29. **test_views.py** (Line 16)
   - From module: models
30. **validators.py** (Line 19)
   - From module: models
31. **views.py** (Line 61)
   - From module: models

### models.EnhancedClickTracker

1. **serializers.py** (Line 58)
   - From module: models
2. **services.py** (Line 25)
   - From module: models
3. **signals.py** (Line 31)
   - From module: models
4. **views.py** (Line 61)
   - From module: models

### models.FraudPattern

1. **serializers.py** (Line 58)
   - From module: models
2. **serializers.py** (Line 9006)
   - From module: models
3. **services.py** (Line 25)
   - From module: models
4. **signals.py** (Line 31)
   - From module: models
5. **views.py** (Line 61)
   - From module: models

### models.GeolocationLog

1. **filters.py** (Line 15)
   - From module: models
2. **serializers.py** (Line 58)
   - From module: models
3. **services.py** (Line 25)
   - From module: models
4. **signals.py** (Line 31)
   - From module: models
5. **views.py** (Line 61)
   - From module: models
6. **views.py** (Line 2121)
   - From module: models
7. **views.py** (Line 3024)
   - From module: models
8. **views.py** (Line 3329)
   - From module: models
9. **views.py** (Line 2510)
   - From module: models

### models.IPBlacklist

1. **admin.py** (Line 6641)
   - From module: models
2. **admin.py** (Line 7317)
   - From module: models
3. **admin.py** (Line 7381)
   - From module: models
4. **apps.py** (Line 81)
   - From module: models
5. **common_imports.py** (Line 142)
   - From module: models
6. **consumers.py** (Line 489)
   - From module: models
7. **factories.py** (Line 13)
   - From module: models
8. **factories_backup.py** (Line 13)
   - From module: models
9. **filters.py** (Line 15)
   - From module: models
10. **fixtures.py** (Line 10)
   - From module: models
11. **forms.py** (Line 12)
   - From module: models
12. **logic.py** (Line 119)
   - From module: models
13. **permissions.py** (Line 20)
   - From module: models
14. **permissions_backup.py** (Line 20)
   - From module: models
15. **receivers.py** (Line 17)
   - From module: models
16. **serializers.py** (Line 24)
   - From module: models
17. **serializers.py** (Line 58)
   - From module: models
18. **services.py** (Line 25)
   - From module: models
19. **signals.py** (Line 31)
   - From module: models
20. **test_models.py** (Line 13)
   - From module: models
21. **test_serializers.py** (Line 15)
   - From module: models
22. **test_views.py** (Line 16)
   - From module: models
23. **validators.py** (Line 19)
   - From module: models
24. **views.py** (Line 17)
   - From module: models
25. **views.py** (Line 61)
   - From module: models

### models.MaintenanceMode

1. **decorators.py** (Line 22)
   - From module: models
2. **serializers.py** (Line 58)
   - From module: models
3. **views.py** (Line 61)
   - From module: models

### models.PasswordAttempt

1. **serializers.py** (Line 58)
   - From module: models
2. **views.py** (Line 61)
   - From module: models

### models.PasswordHistory

1. **apps.py** (Line 81)
   - From module: models
2. **common_imports.py** (Line 142)
   - From module: models
3. **factories.py** (Line 13)
   - From module: models
4. **factories_backup.py** (Line 13)
   - From module: models
5. **filters.py** (Line 15)
   - From module: models
6. **fixtures.py** (Line 10)
   - From module: models
7. **permissions.py** (Line 20)
   - From module: models
8. **permissions_backup.py** (Line 20)
   - From module: models
9. **receivers.py** (Line 17)
   - From module: models
10. **serializers.py** (Line 58)
   - From module: models
11. **services.py** (Line 25)
   - From module: models
12. **signals.py** (Line 31)
   - From module: models
13. **test_models.py** (Line 13)
   - From module: models
14. **test_serializers.py** (Line 15)
   - From module: models
15. **test_views.py** (Line 16)
   - From module: models
16. **validators.py** (Line 19)
   - From module: models
17. **views.py** (Line 61)
   - From module: models

### models.PasswordPolicy

1. **apps.py** (Line 81)
   - From module: models
2. **forms.py** (Line 12)
   - From module: models
3. **serializers.py** (Line 58)
   - From module: models
4. **views.py** (Line 61)
   - From module: models
5. **views.py** (Line 3958)
   - From module: models

### models.RateLimitLog

1. **serializers.py** (Line 58)
   - From module: models
2. **services.py** (Line 25)
   - From module: models
3. **signals.py** (Line 31)
   - From module: models
4. **views.py** (Line 61)
   - From module: models

### models.RealTimeDetection

1. **serializers.py** (Line 58)
   - From module: models
2. **serializers.py** (Line 9700)
   - From module: models
3. **serializers.py** (Line 11080)
   - From module: models
4. **services.py** (Line 25)
   - From module: models
5. **signals.py** (Line 31)
   - From module: models
6. **views.py** (Line 61)
   - From module: models

### models.RiskScore

1. **admin.py** (Line 6641)
   - From module: models
2. **admin.py** (Line 7332)
   - From module: models
3. **apps.py** (Line 81)
   - From module: models
4. **common_imports.py** (Line 142)
   - From module: models
5. **consumers.py** (Line 549)
   - From module: models
6. **factories.py** (Line 13)
   - From module: models
7. **factories_backup.py** (Line 13)
   - From module: models
8. **filters.py** (Line 15)
   - From module: models
9. **fixtures.py** (Line 10)
   - From module: models
10. **mixins.py** (Line 21)
   - From module: models
11. **permissions_backup.py** (Line 372)
   - From module: models
12. **receivers.py** (Line 17)
   - From module: models
13. **serializers.py** (Line 58)
   - From module: models
14. **services.py** (Line 25)
   - From module: models
15. **signals.py** (Line 31)
   - From module: models
16. **test_models.py** (Line 13)
   - From module: models
17. **test_serializers.py** (Line 15)
   - From module: models
18. **test_views.py** (Line 16)
   - From module: models
19. **views.py** (Line 61)
   - From module: models

### models.SecurityDashboard

1. **serializers.py** (Line 58)
   - From module: models
2. **views.py** (Line 61)
   - From module: models

### models.SecurityIncident

1. **analytics.py** (Line 16)
   - From module: models
2. **apps.py** (Line 81)
   - From module: models
3. **caching.py** (Line 18)
   - From module: models
4. **common_imports.py** (Line 142)
   - From module: models
5. **compliance.py** (Line 15)
   - From module: models
6. **consumers.py** (Line 489)
   - From module: models
7. **context_processors.py** (Line 12)
   - From module: models
8. **data_export.py** (Line 19)
   - From module: models
9. **endpoint.py** (Line 324)
   - From module: models
10. **events.py** (Line 17)
   - From module: models
11. **factories.py** (Line 13)
   - From module: models
12. **factories_backup.py** (Line 13)
   - From module: models
13. **filters.py** (Line 15)
   - From module: models
14. **fixtures.py** (Line 10)
   - From module: models
15. **hooks.py** (Line 15)
   - From module: models
16. **logic.py** (Line 14)
   - From module: models
17. **monitoring.py** (Line 18)
   - From module: models
18. **notifications_push.py** (Line 16)
   - From module: models
19. **permissions.py** (Line 20)
   - From module: models
20. **permissions_backup.py** (Line 20)
   - From module: models
21. **receivers.py** (Line 17)
   - From module: models
22. **repositories.py** (Line 14)
   - From module: models
23. **sanctions.py** (Line 15)
   - From module: models
24. **selectors.py** (Line 339)
   - From module: models
25. **services.py** (Line 25)
   - From module: models
26. **signals.py** (Line 31)
   - From module: models
27. **signals_cap.py** (Line 17)
   - From module: models
28. **signals_kb.py** (Line 16)
   - From module: models
29. **tasks_cap.py** (Line 19)
   - From module: models
30. **test_models.py** (Line 13)
   - From module: models
31. **test_serializers.py** (Line 15)
   - From module: models
32. **test_views.py** (Line 16)
   - From module: models
33. **use_cases.py** (Line 14)
   - From module: models
34. **views.py** (Line 61)
   - From module: models
35. **webhooks.py** (Line 22)
   - From module: models
36. **integration_system\auth_bridge.py** (Line 17)
   - From module: models
37. **integration_system\bridge.py** (Line 16)
   - From module: models
38. **integration_system\circuit_breaker.py** (Line 16)
   - From module: models
39. **integration_system\data_bridge.py** (Line 16)
   - From module: models
40. **integration_system\data_validator.py** (Line 17)
   - From module: models
41. **integration_system\event_bus.py** (Line 17)
   - From module: models
42. **integration_system\fallback_logic.py** (Line 16)
   - From module: models
43. **integration_system\health_check.py** (Line 16)
   - From module: models
44. **integration_system\integ_adapter.py** (Line 15)
   - From module: models
45. **integration_system\integ_audit_logs.py** (Line 16)
   - From module: models
46. **integration_system\integ_exceptions.py** (Line 492)
   - From module: models
47. **integration_system\integ_handler.py** (Line 16)
   - From module: models
48. **integration_system\integ_registry.py** (Line 15)
   - From module: models
49. **integration_system\integ_signals.py** (Line 16)
   - From module: models
50. **integration_system\message_queue.py** (Line 18)
   - From module: models
51. **integration_system\performance_monitor.py** (Line 17)
   - From module: models
52. **integration_system\sync_manager.py** (Line 15)
   - From module: models
53. **integration_system\transformer.py** (Line 17)
   - From module: models
54. **integration_system\versioning.py** (Line 15)
   - From module: models
55. **integration_system\webhooks_integration.py** (Line 25)
   - From module: models

### models.SecurityInsight

1. **apps.py** (Line 81)
   - From module: models
2. **common_imports.py** (Line 142)
   - From module: models
3. **factories.py** (Line 13)
   - From module: models
4. **factories_backup.py** (Line 13)
   - From module: models
5. **filters.py** (Line 15)
   - From module: models
6. **fixtures.py** (Line 10)
   - From module: models
7. **permissions.py** (Line 20)
   - From module: models
8. **permissions_backup.py** (Line 20)
   - From module: models
9. **services.py** (Line 25)
   - From module: models
10. **signals.py** (Line 31)
   - From module: models
11. **test_models.py** (Line 13)
   - From module: models
12. **test_serializers.py** (Line 15)
   - From module: models
13. **test_views.py** (Line 16)
   - From module: models
14. **views.py** (Line 61)
   - From module: models

### models.SecurityLog

1. **admin.py** (Line 6641)
   - From module: models
2. **admin.py** (Line 7264)
   - From module: models
3. **admin.py** (Line 7358)
   - From module: models
4. **analytics.py** (Line 16)
   - From module: models
5. **attachment_upload_view.py** (Line 276)
   - From module: models
6. **caching.py** (Line 18)
   - From module: models
7. **common_imports.py** (Line 142)
   - From module: models
8. **compliance.py** (Line 15)
   - From module: models
9. **consumers.py** (Line 311)
   - From module: models
10. **consumers.py** (Line 489)
   - From module: models
11. **consumers.py** (Line 549)
   - From module: models
12. **context_processors.py** (Line 12)
   - From module: models
13. **data_export.py** (Line 19)
   - From module: models
14. **decorators.py** (Line 22)
   - From module: models
15. **endpoint.py** (Line 324)
   - From module: models
16. **events.py** (Line 17)
   - From module: models
17. **factories.py** (Line 13)
   - From module: models
18. **factories_backup.py** (Line 13)
   - From module: models
19. **filters.py** (Line 15)
   - From module: models
20. **fixtures.py** (Line 10)
   - From module: models
21. **hooks.py** (Line 15)
   - From module: models
22. **logic.py** (Line 14)
   - From module: models
23. **mixins.py** (Line 21)
   - From module: models
24. **models.py** (Line 341)
   - From module: models
25. **model_mixins.py** (Line 208)
   - From module: models
26. **monitoring.py** (Line 18)
   - From module: models
27. **notifications_push.py** (Line 16)
   - From module: models
28. **permissions.py** (Line 20)
   - From module: models
29. **permissions_backup.py** (Line 20)
   - From module: models
30. **receivers.py** (Line 17)
   - From module: models
31. **repositories.py** (Line 14)
   - From module: models
32. **sanctions.py** (Line 15)
   - From module: models
33. **search.py** (Line 605)
   - From module: models
34. **search.py** (Line 625)
   - From module: models
35. **search.py** (Line 648)
   - From module: models
36. **selectors.py** (Line 75)
   - From module: models
37. **serializers.py** (Line 31)
   - From module: models
38. **serializers.py** (Line 58)
   - From module: models
39. **services.py** (Line 25)
   - From module: models
40. **signals.py** (Line 31)
   - From module: models
41. **signals_cap.py** (Line 17)
   - From module: models
42. **signals_kb.py** (Line 16)
   - From module: models
43. **tasks_cap.py** (Line 19)
   - From module: models
44. **test_models.py** (Line 13)
   - From module: models
45. **test_serializers.py** (Line 15)
   - From module: models
46. **test_views.py** (Line 16)
   - From module: models
47. **throttling.py** (Line 124)
   - From module: models
48. **use_cases.py** (Line 14)
   - From module: models
49. **utils.py** (Line 261)
   - From module: models
50. **validators.py** (Line 340)
   - From module: models
51. **views.py** (Line 61)
   - From module: models
52. **views.py** (Line 8649)
   - From module: models
53. **viewset.py** (Line 237)
   - From module: models
54. **viewset_cap.py** (Line 474)
   - From module: models
55. **webhooks.py** (Line 22)
   - From module: models
56. **integration_system\auth_bridge.py** (Line 17)
   - From module: models
57. **integration_system\bridge.py** (Line 16)
   - From module: models
58. **integration_system\circuit_breaker.py** (Line 16)
   - From module: models
59. **integration_system\data_bridge.py** (Line 16)
   - From module: models
60. **integration_system\data_validator.py** (Line 17)
   - From module: models
61. **integration_system\event_bus.py** (Line 17)
   - From module: models
62. **integration_system\fallback_logic.py** (Line 16)
   - From module: models
63. **integration_system\health_check.py** (Line 16)
   - From module: models
64. **integration_system\integ_adapter.py** (Line 15)
   - From module: models
65. **integration_system\integ_audit_logs.py** (Line 16)
   - From module: models
66. **integration_system\integ_handler.py** (Line 16)
   - From module: models
67. **integration_system\integ_registry.py** (Line 15)
   - From module: models
68. **integration_system\integ_signals.py** (Line 16)
   - From module: models
69. **integration_system\message_queue.py** (Line 18)
   - From module: models
70. **integration_system\performance_monitor.py** (Line 17)
   - From module: models
71. **integration_system\sync_manager.py** (Line 15)
   - From module: models
72. **integration_system\transformer.py** (Line 17)
   - From module: models
73. **integration_system\versioning.py** (Line 15)
   - From module: models
74. **integration_system\webhooks_integration.py** (Line 25)
   - From module: models

### models.SecurityNotification

1. **common_imports.py** (Line 142)
   - From module: models
2. **factories.py** (Line 13)
   - From module: models
3. **factories_backup.py** (Line 13)
   - From module: models
4. **fixtures.py** (Line 10)
   - From module: models
5. **serializers.py** (Line 58)
   - From module: models
6. **test_models.py** (Line 13)
   - From module: models
7. **views.py** (Line 61)
   - From module: models

### models.SecurityPolicy

1. **apps.py** (Line 81)
   - From module: models
2. **common_imports.py** (Line 142)
   - From module: models
3. **factories.py** (Line 13)
   - From module: models
4. **factories_backup.py** (Line 13)
   - From module: models
5. **filters.py** (Line 15)
   - From module: models
6. **fixtures.py** (Line 10)
   - From module: models
7. **forms.py** (Line 12)
   - From module: models
8. **permissions.py** (Line 20)
   - From module: models
9. **permissions_backup.py** (Line 20)
   - From module: models
10. **services.py** (Line 25)
   - From module: models
11. **signals.py** (Line 31)
   - From module: models
12. **test_models.py** (Line 13)
   - From module: models
13. **test_serializers.py** (Line 15)
   - From module: models
14. **test_views.py** (Line 16)
   - From module: models
15. **views.py** (Line 61)
   - From module: models

### models.SessionActivity

1. **serializers.py** (Line 58)
   - From module: models
2. **services.py** (Line 25)
   - From module: models
3. **signals.py** (Line 31)
   - From module: models
4. **views.py** (Line 61)
   - From module: models

### models.ThreatIntelligence

1. **analytics.py** (Line 16)
   - From module: models
2. **apps.py** (Line 81)
   - From module: models
3. **caching.py** (Line 18)
   - From module: models
4. **caching.py** (Line 517)
   - From module: models
5. **common_imports.py** (Line 142)
   - From module: models
6. **context_processors.py** (Line 12)
   - From module: models
7. **data_export.py** (Line 19)
   - From module: models
8. **events.py** (Line 17)
   - From module: models
9. **factories.py** (Line 13)
   - From module: models
10. **factories_backup.py** (Line 13)
   - From module: models
11. **filters.py** (Line 15)
   - From module: models
12. **fixtures.py** (Line 10)
   - From module: models
13. **hooks.py** (Line 15)
   - From module: models
14. **logic.py** (Line 14)
   - From module: models
15. **monitoring.py** (Line 18)
   - From module: models
16. **permissions.py** (Line 20)
   - From module: models
17. **permissions_backup.py** (Line 20)
   - From module: models
18. **repositories.py** (Line 14)
   - From module: models
19. **selectors.py** (Line 483)
   - From module: models
20. **services.py** (Line 25)
   - From module: models
21. **signals.py** (Line 31)
   - From module: models
22. **signals_cap.py** (Line 17)
   - From module: models
23. **signals_kb.py** (Line 16)
   - From module: models
24. **tasks_cap.py** (Line 19)
   - From module: models
25. **test_models.py** (Line 13)
   - From module: models
26. **test_serializers.py** (Line 15)
   - From module: models
27. **test_views.py** (Line 16)
   - From module: models
28. **throttling.py** (Line 398)
   - From module: models
29. **use_cases.py** (Line 14)
   - From module: models
30. **validators.py** (Line 19)
   - From module: models
31. **views.py** (Line 61)
   - From module: models
32. **integration_system\webhooks_integration.py** (Line 545)
   - From module: models

### models.TrustedDevice

1. **apps.py** (Line 81)
   - From module: models
2. **common_imports.py** (Line 142)
   - From module: models
3. **factories.py** (Line 13)
   - From module: models
4. **factories_backup.py** (Line 13)
   - From module: models
5. **filters.py** (Line 15)
   - From module: models
6. **fixtures.py** (Line 10)
   - From module: models
7. **forms.py** (Line 12)
   - From module: models
8. **permissions.py** (Line 20)
   - From module: models
9. **permissions_backup.py** (Line 20)
   - From module: models
10. **services.py** (Line 25)
   - From module: models
11. **signals.py** (Line 31)
   - From module: models
12. **test_models.py** (Line 13)
   - From module: models
13. **test_serializers.py** (Line 15)
   - From module: models
14. **test_views.py** (Line 16)
   - From module: models
15. **validators.py** (Line 19)
   - From module: models
16. **views.py** (Line 61)
   - From module: models

### models.TwoFactorAttempt

1. **serializers.py** (Line 58)
   - From module: models
2. **services.py** (Line 25)
   - From module: models
3. **signals.py** (Line 31)
   - From module: models
4. **views.py** (Line 61)
   - From module: models

### models.TwoFactorMethod

1. **common_imports.py** (Line 142)
   - From module: models
2. **factories.py** (Line 13)
   - From module: models
3. **factories_backup.py** (Line 13)
   - From module: models
4. **fixtures.py** (Line 10)
   - From module: models
5. **serializers.py** (Line 58)
   - From module: models
6. **services.py** (Line 25)
   - From module: models
7. **signals.py** (Line 31)
   - From module: models
8. **test_models.py** (Line 13)
   - From module: models
9. **views.py** (Line 61)
   - From module: models

### models.TwoFactorRecoveryCode

1. **serializers.py** (Line 58)
   - From module: models
2. **services.py** (Line 25)
   - From module: models
3. **signals.py** (Line 31)
   - From module: models
4. **views.py** (Line 61)
   - From module: models

### models.UserBan

1. **admin.py** (Line 6641)
   - From module: models
2. **admin.py** (Line 7300)
   - From module: models
3. **admin.py** (Line 7375)
   - From module: models
4. **analytics.py** (Line 16)
   - From module: models
5. **apps.py** (Line 81)
   - From module: models
6. **caching.py** (Line 438)
   - From module: models
7. **common_imports.py** (Line 142)
   - From module: models
8. **consumers.py** (Line 489)
   - From module: models
9. **context_processors.py** (Line 344)
   - From module: models
10. **data_export.py** (Line 19)
   - From module: models
11. **factories.py** (Line 13)
   - From module: models
12. **factories_backup.py** (Line 13)
   - From module: models
13. **filters.py** (Line 15)
   - From module: models
14. **fixtures.py** (Line 10)
   - From module: models
15. **logic.py** (Line 14)
   - From module: models
16. **permissions.py** (Line 20)
   - From module: models
17. **permissions_backup.py** (Line 20)
   - From module: models
18. **repositories.py** (Line 14)
   - From module: models
19. **sanctions.py** (Line 15)
   - From module: models
20. **selectors.py** (Line 591)
   - From module: models
21. **serializers.py** (Line 58)
   - From module: models
22. **services.py** (Line 25)
   - From module: models
23. **signals.py** (Line 31)
   - From module: models
24. **tasks_cap.py** (Line 19)
   - From module: models
25. **test_models.py** (Line 13)
   - From module: models
26. **test_serializers.py** (Line 15)
   - From module: models
27. **test_views.py** (Line 16)
   - From module: models
28. **use_cases.py** (Line 14)
   - From module: models
29. **views.py** (Line 61)
   - From module: models

### models.UserSession

1. **common_imports.py** (Line 142)
   - From module: models
2. **factories.py** (Line 13)
   - From module: models
3. **factories_backup.py** (Line 13)
   - From module: models
4. **fixtures.py** (Line 10)
   - From module: models
5. **mixins.py** (Line 21)
   - From module: models
6. **receivers.py** (Line 17)
   - From module: models
7. **serializers.py** (Line 58)
   - From module: models
8. **services.py** (Line 25)
   - From module: models
9. **signals.py** (Line 31)
   - From module: models
10. **test_models.py** (Line 13)
   - From module: models
11. **test_serializers.py** (Line 15)
   - From module: models
12. **test_views.py** (Line 16)
   - From module: models
13. **views.py** (Line 61)
   - From module: models

### models.WithdrawalProtection

1. **apps.py** (Line 81)
   - From module: models
2. **serializers.py** (Line 58)
   - From module: models
3. **views.py** (Line 61)
   - From module: models

### monitoring.monitoring_manager

1. **context_processors.py** (Line 14)
   - From module: monitoring
2. **events.py** (Line 20)
   - From module: monitoring
3. **hooks.py** (Line 18)
   - From module: monitoring
4. **signals_cap.py** (Line 20)
   - From module: monitoring
5. **tasks_cap.py** (Line 22)
   - From module: monitoring
6. **integration_system\integ_handler.py** (Line 18)
   - From module: monitoring

### notifications_push.notification_service

1. **tasks_cap.py** (Line 455)
   - From module: notifications_push
2. **tasks_cap.py** (Line 510)
   - From module: notifications_push
3. **tasks_cap.py** (Line 487)
   - From module: notifications_push

### openpyxl.styles.Font

1. **common_imports.py** (Line 132)
   - From module: openpyxl.styles
2. **management\commands\export_security_report.py** (Line 724)
   - From module: openpyxl.styles

### os

1. **attachment_upload_view.py** (Line 8)
   - From module: os
2. **celery_beat_config.py** (Line 10)
   - From module: os
3. **common_imports.py** (Line 20)
   - From module: os
4. **duplicate_analyzer.py** (Line 7)
   - From module: os
5. **encryption.py** (Line 7)
   - From module: os
6. **monitoring.py** (Line 547)
   - From module: os
7. **resources.py** (Line 265)
   - From module: os
8. **resources.py** (Line 274)
   - From module: os
9. **serializers.py** (Line 1634)
   - From module: os
10. **tasks.py** (Line 608)
   - From module: os
11. **integration_system\data_bridge.py** (Line 377)
   - From module: os
12. **integration_system\data_bridge.py** (Line 554)
   - From module: os
13. **tests\test_threat_intel.py** (Line 873)
   - From module: os
14. **tests\test_vpn_detector.py** (Line 752)
   - From module: os
15. **utils\cache_manager.py** (Line 979)
   - From module: os

### permissions.IsSecurityAdmin

1. **endpoint.py** (Line 21)
   - From module: permissions
2. **views.py** (Line 42)
   - From module: permissions
3. **viewset.py** (Line 22)
   - From module: permissions

### pika

1. **integration_system\integ_adapter.py** (Line 447)
   - From module: pika
2. **integration_system\integ_adapter.py** (Line 474)
   - From module: pika
3. **integration_system\integ_adapter.py** (Line 414)
   - From module: pika

### psutil

1. **analytics.py** (Line 471)
   - From module: psutil
2. **analytics.py** (Line 895)
   - From module: psutil
3. **monitoring.py** (Line 566)
   - From module: psutil
4. **plugins.py** (Line 641)
   - From module: psutil
5. **plugins.py** (Line 676)
   - From module: psutil
6. **views.py** (Line 8723)
   - From module: psutil
7. **views.py** (Line 8760)
   - From module: psutil
8. **integration_system\performance_monitor.py** (Line 8)
   - From module: psutil
9. **tests\test_threat_intel.py** (Line 872)
   - From module: psutil
10. **tests\test_vpn_detector.py** (Line 751)
   - From module: psutil

### pyotp

1. **serializers.py** (Line 2496)
   - From module: pyotp
2. **serializers.py** (Line 2608)
   - From module: pyotp
3. **views.py** (Line 9533)
   - From module: pyotp

### pytest

1. **test_models.py** (Line 6)
   - From module: pytest
2. **test_serializers.py** (Line 6)
   - From module: pytest
3. **test_views.py** (Line 6)
   - From module: pytest

### querysets.SecurityLogQuerySet

1. **repositories.py** (Line 19)
   - From module: querysets
2. **selectors.py** (Line 13)
   - From module: querysets

### querysets.SecurityQuerySet

1. **repositories.py** (Line 19)
   - From module: querysets
2. **selectors.py** (Line 13)
   - From module: querysets

### random

1. **factories.py** (Line 6)
   - From module: random
2. **factories_backup.py** (Line 6)
   - From module: random

### re

1. **common_imports.py** (Line 13)
   - From module: re
2. **duplicate_analyzer.py** (Line 9)
   - From module: re
3. **models.py** (Line 32)
   - From module: re
4. **models.py** (Line 4817)
   - From module: re
5. **search.py** (Line 7)
   - From module: re
6. **serializers.py** (Line 8711)
   - From module: re
7. **serializers.py** (Line 2981)
   - From module: re
8. **serializers.py** (Line 3842)
   - From module: re
9. **utils.py** (Line 10)
   - From module: re
10. **validators.py** (Line 8)
   - From module: re
11. **integration_system\data_validator.py** (Line 7)
   - From module: re
12. **services\SecurityPolicyService.py** (Line 378)
   - From module: re
13. **utils\security_helpers.py** (Line 9)
   - From module: re

### registry.ComponentType

1. **endpoint.py** (Line 20)
   - From module: registry
2. **resources.py** (Line 15)
   - From module: registry
3. **throttling.py** (Line 19)
   - From module: registry
4. **viewset_cap.py** (Line 16)
   - From module: registry

### registry.security_registry

1. **endpoint.py** (Line 20)
   - From module: registry
2. **resources.py** (Line 15)
   - From module: registry
3. **throttling.py** (Line 19)
   - From module: registry
4. **viewset.py** (Line 21)
   - From module: registry
5. **viewset_cap.py** (Line 16)
   - From module: registry

### reportlab.lib.pagesizes.A4

1. **common_imports.py** (Line 135)
   - From module: reportlab.lib.pagesizes
2. **management\commands\export_security_report.py** (Line 788)
   - From module: reportlab.lib.pagesizes

### reportlab.lib.pagesizes.letter

1. **common_imports.py** (Line 135)
   - From module: reportlab.lib.pagesizes
2. **management\commands\export_security_report.py** (Line 788)
   - From module: reportlab.lib.pagesizes

### reportlab.lib.styles.getSampleStyleSheet

1. **common_imports.py** (Line 137)
   - From module: reportlab.lib.styles
2. **management\commands\export_security_report.py** (Line 790)
   - From module: reportlab.lib.styles

### reportlab.lib.units.inch

1. **common_imports.py** (Line 136)
   - From module: reportlab.lib.units
2. **management\commands\export_security_report.py** (Line 791)
   - From module: reportlab.lib.units

### reportlab.platypus.Paragraph

1. **common_imports.py** (Line 138)
   - From module: reportlab.platypus
2. **management\commands\export_security_report.py** (Line 789)
   - From module: reportlab.platypus

### reportlab.platypus.SimpleDocTemplate

1. **common_imports.py** (Line 138)
   - From module: reportlab.platypus
2. **management\commands\export_security_report.py** (Line 789)
   - From module: reportlab.platypus

### reportlab.platypus.Spacer

1. **common_imports.py** (Line 138)
   - From module: reportlab.platypus
2. **management\commands\export_security_report.py** (Line 789)
   - From module: reportlab.platypus

### requests

1. **dependencies.py** (Line 9)
   - From module: requests
2. **monitoring.py** (Line 730)
   - From module: requests
3. **notifications_push.py** (Line 531)
   - From module: requests
4. **notifications_push.py** (Line 566)
   - From module: requests
5. **resources.py** (Line 304)
   - From module: requests
6. **resources.py** (Line 317)
   - From module: requests
7. **resources.py** (Line 342)
   - From module: requests
8. **resources.py** (Line 440)
   - From module: requests
9. **resources.py** (Line 450)
   - From module: requests
10. **webhooks.py** (Line 19)
   - From module: requests
11. **integration_system\data_bridge.py** (Line 347)
   - From module: requests
12. **integration_system\data_bridge.py** (Line 512)
   - From module: requests
13. **integration_system\health_check.py** (Line 224)
   - From module: requests
14. **integration_system\integ_adapter.py** (Line 207)
   - From module: requests
15. **integration_system\webhooks_integration.py** (Line 174)
   - From module: requests
16. **integration_system\webhooks_integration.py** (Line 328)
   - From module: requests
17. **utils\device.py** (Line 1)
   - From module: requests

### requests.exceptions.RequestException

1. **common_imports.py** (Line 120)
   - From module: requests.exceptions
2. **webhooks.py** (Line 20)
   - From module: requests.exceptions

### rest_framework.decorators.action

1. **common_imports.py** (Line 76)
   - From module: rest_framework.decorators
2. **serializers.py** (Line 39)
   - From module: rest_framework.decorators
3. **views.py** (Line 36)
   - From module: rest_framework.decorators
4. **viewset.py** (Line 9)
   - From module: rest_framework.decorators
5. **viewset_cap.py** (Line 9)
   - From module: rest_framework.decorators

### rest_framework.decorators.api_view

1. **common_imports.py** (Line 76)
   - From module: rest_framework.decorators
2. **endpoint.py** (Line 15)
   - From module: rest_framework.decorators
3. **serializers.py** (Line 39)
   - From module: rest_framework.decorators
4. **views.py** (Line 36)
   - From module: rest_framework.decorators

### rest_framework.decorators.permission_classes

1. **common_imports.py** (Line 76)
   - From module: rest_framework.decorators
2. **endpoint.py** (Line 15)
   - From module: rest_framework.decorators
3. **serializers.py** (Line 39)
   - From module: rest_framework.decorators
4. **views.py** (Line 36)
   - From module: rest_framework.decorators

### rest_framework.exceptions.AuthenticationFailed

1. **views.py** (Line 5092)
   - From module: rest_framework.exceptions
2. **views.py** (Line 382)
   - From module: rest_framework.exceptions

### rest_framework.exceptions.NotAuthenticated

1. **views.py** (Line 5092)
   - From module: rest_framework.exceptions
2. **views.py** (Line 382)
   - From module: rest_framework.exceptions

### rest_framework.exceptions.NotFound

1. **common_imports.py** (Line 88)
   - From module: rest_framework.exceptions
2. **views.py** (Line 29)
   - From module: rest_framework.exceptions
3. **views.py** (Line 39)
   - From module: rest_framework.exceptions
4. **views.py** (Line 382)
   - From module: rest_framework.exceptions

### rest_framework.exceptions.PermissionDenied

1. **permissions.py** (Line 413)
   - From module: rest_framework.exceptions
2. **permissions.py** (Line 432)
   - From module: rest_framework.exceptions
3. **validators.py** (Line 16)
   - From module: rest_framework.exceptions
4. **views.py** (Line 29)
   - From module: rest_framework.exceptions
5. **views.py** (Line 39)
   - From module: rest_framework.exceptions
6. **views.py** (Line 382)
   - From module: rest_framework.exceptions

### rest_framework.exceptions.Throttled

1. **common_imports.py** (Line 274)
   - From module: rest_framework.exceptions
2. **views.py** (Line 39)
   - From module: rest_framework.exceptions

### rest_framework.exceptions.ValidationError

1. **filters.py** (Line 13)
   - From module: rest_framework.exceptions
2. **views.py** (Line 29)
   - From module: rest_framework.exceptions
3. **views.py** (Line 39)
   - From module: rest_framework.exceptions
4. **views.py** (Line 382)
   - From module: rest_framework.exceptions

### rest_framework.filters.OrderingFilter

1. **common_imports.py** (Line 83)
   - From module: rest_framework.filters
2. **views.py** (Line 44)
   - From module: rest_framework.filters
3. **viewset.py** (Line 17)
   - From module: rest_framework.filters

### rest_framework.filters.SearchFilter

1. **common_imports.py** (Line 83)
   - From module: rest_framework.filters
2. **views.py** (Line 44)
   - From module: rest_framework.filters
3. **viewset.py** (Line 17)
   - From module: rest_framework.filters

### rest_framework.generics

1. **common_imports.py** (Line 75)
   - From module: rest_framework
2. **views.py** (Line 28)
   - From module: rest_framework

### rest_framework.pagination.LimitOffsetPagination

1. **common_imports.py** (Line 82)
   - From module: rest_framework.pagination
2. **pagination.py** (Line 9)
   - From module: rest_framework.pagination
3. **views.py** (Line 38)
   - From module: rest_framework.pagination

### rest_framework.pagination.PageNumberPagination

1. **common_imports.py** (Line 82)
   - From module: rest_framework.pagination
2. **pagination.py** (Line 9)
   - From module: rest_framework.pagination
3. **views.py** (Line 38)
   - From module: rest_framework.pagination
4. **viewset.py** (Line 11)
   - From module: rest_framework.pagination

### rest_framework.permissions

1. **common_imports.py** (Line 75)
   - From module: rest_framework
2. **permissions.py** (Line 8)
   - From module: rest_framework
3. **permissions_backup.py** (Line 8)
   - From module: rest_framework
4. **views.py** (Line 28)
   - From module: rest_framework
5. **views.py** (Line 35)
   - From module: rest_framework
6. **viewset.py** (Line 8)
   - From module: rest_framework
7. **viewset_cap.py** (Line 8)
   - From module: rest_framework

### rest_framework.permissions.BasePermission

1. **common_imports.py** (Line 84)
   - From module: rest_framework.permissions
2. **mixins.py** (Line 17)
   - From module: rest_framework.permissions
3. **views.py** (Line 13)
   - From module: rest_framework.permissions

### rest_framework.permissions.IsAdminUser

1. **common_imports.py** (Line 84)
   - From module: rest_framework.permissions
2. **serializers.py** (Line 41)
   - From module: rest_framework.permissions
3. **views.py** (Line 40)
   - From module: rest_framework.permissions

### rest_framework.permissions.IsAuthenticated

1. **attachment_upload_view.py** (Line 23)
   - From module: rest_framework.permissions
2. **common_imports.py** (Line 84)
   - From module: rest_framework.permissions
3. **endpoint.py** (Line 16)
   - From module: rest_framework.permissions
4. **serializers.py** (Line 41)
   - From module: rest_framework.permissions
5. **views.py** (Line 40)
   - From module: rest_framework.permissions

### rest_framework.response.Response

1. **attachment_upload_view.py** (Line 21)
   - From module: rest_framework.response
2. **common_imports.py** (Line 77)
   - From module: rest_framework.response
3. **endpoint.py** (Line 17)
   - From module: rest_framework.response
4. **mixins.py** (Line 16)
   - From module: rest_framework.response
5. **pagination.py** (Line 10)
   - From module: rest_framework.response
6. **permissions_backup.py** (Line 626)
   - From module: rest_framework.response
7. **permissions_backup.py** (Line 648)
   - From module: rest_framework.response
8. **serializers.py** (Line 40)
   - From module: rest_framework.response
9. **views.py** (Line 37)
   - From module: rest_framework.response
10. **views.py** (Line 9849)
   - From module: rest_framework.response
11. **views.py** (Line 8966)
   - From module: rest_framework.response
12. **views.py** (Line 8970)
   - From module: rest_framework.response
13. **views.py** (Line 392)
   - From module: rest_framework.response
14. **viewset.py** (Line 10)
   - From module: rest_framework.response
15. **viewset_cap.py** (Line 10)
   - From module: rest_framework.response
16. **integration_system\webhooks_integration.py** (Line 22)
   - From module: rest_framework.response

### rest_framework.serializers

1. **common_imports.py** (Line 75)
   - From module: rest_framework
2. **serializers.py** (Line 27)
   - From module: rest_framework
3. **serializers.py** (Line 8705)
   - From module: rest_framework
4. **test_serializers.py** (Line 12)
   - From module: rest_framework
5. **views.py** (Line 35)
   - From module: rest_framework

### rest_framework.status

1. **attachment_upload_view.py** (Line 22)
   - From module: rest_framework
2. **common_imports.py** (Line 75)
   - From module: rest_framework
3. **endpoint.py** (Line 18)
   - From module: rest_framework
4. **mixins.py** (Line 15)
   - From module: rest_framework
5. **permissions_backup.py** (Line 627)
   - From module: rest_framework
6. **permissions_backup.py** (Line 649)
   - From module: rest_framework
7. **serializers.py** (Line 38)
   - From module: rest_framework
8. **tests.py** (Line 23)
   - From module: rest_framework
9. **test_views.py** (Line 12)
   - From module: rest_framework
10. **views.py** (Line 28)
   - From module: rest_framework
11. **views.py** (Line 35)
   - From module: rest_framework
12. **views.py** (Line 393)
   - From module: rest_framework
13. **viewset.py** (Line 8)
   - From module: rest_framework
14. **viewset_cap.py** (Line 8)
   - From module: rest_framework
15. **webhooks.py** (Line 18)
   - From module: rest_framework
16. **integration_system\webhooks_integration.py** (Line 23)
   - From module: rest_framework
17. **tests\test_security_views.py** (Line 15)
   - From module: rest_framework

### rest_framework.test.APIClient

1. **tests.py** (Line 22)
   - From module: rest_framework.test
2. **test_views.py** (Line 11)
   - From module: rest_framework.test
3. **tests\test_security_views.py** (Line 14)
   - From module: rest_framework.test

### rest_framework.test.APITestCase

1. **common_imports.py** (Line 79)
   - From module: rest_framework.test
2. **tests.py** (Line 22)
   - From module: rest_framework.test
3. **test_serializers.py** (Line 11)
   - From module: rest_framework.test
4. **tests\test_incident_service.py** (Line 14)
   - From module: rest_framework.test
5. **tests\test_middleware.py** (Line 15)
   - From module: rest_framework.test
6. **tests\test_password_policy.py** (Line 14)
   - From module: rest_framework.test
7. **tests\test_security_insight.py** (Line 14)
   - From module: rest_framework.test
8. **tests\test_security_models.py** (Line 16)
   - From module: rest_framework.test
9. **tests\test_security_policy.py** (Line 14)
   - From module: rest_framework.test
10. **tests\test_security_views.py** (Line 14)
   - From module: rest_framework.test
11. **tests\test_threat_intel.py** (Line 14)
   - From module: rest_framework.test
12. **tests\test_trusted_device.py** (Line 14)
   - From module: rest_framework.test

### rest_framework.throttling.AnonRateThrottle

1. **common_imports.py** (Line 94)
   - From module: rest_framework.throttling
2. **views.py** (Line 43)
   - From module: rest_framework.throttling

### rest_framework.throttling.BaseThrottle

1. **common_imports.py** (Line 94)
   - From module: rest_framework.throttling
2. **throttling.py** (Line 13)
   - From module: rest_framework.throttling

### rest_framework.throttling.SimpleRateThrottle

1. **common_imports.py** (Line 94)
   - From module: rest_framework.throttling
2. **throttling.py** (Line 13)
   - From module: rest_framework.throttling

### rest_framework.throttling.UserRateThrottle

1. **common_imports.py** (Line 94)
   - From module: rest_framework.throttling
2. **views.py** (Line 43)
   - From module: rest_framework.throttling

### rest_framework.views.APIView

1. **attachment_upload_view.py** (Line 20)
   - From module: rest_framework.views
2. **common_imports.py** (Line 95)
   - From module: rest_framework.views
3. **serializers.py** (Line 42)
   - From module: rest_framework.views
4. **views.py** (Line 30)
   - From module: rest_framework.views
5. **views.py** (Line 41)
   - From module: rest_framework.views
6. **integration_system\webhooks_integration.py** (Line 21)
   - From module: rest_framework.views

### rest_framework.viewsets

1. **common_imports.py** (Line 75)
   - From module: rest_framework
2. **serializers.py** (Line 38)
   - From module: rest_framework
3. **views.py** (Line 28)
   - From module: rest_framework
4. **views.py** (Line 35)
   - From module: rest_framework
5. **viewset.py** (Line 8)
   - From module: rest_framework
6. **viewset_cap.py** (Line 8)
   - From module: rest_framework

### secrets

1. **common_imports.py** (Line 11)
   - From module: secrets
2. **encryption.py** (Line 9)
   - From module: secrets
3. **models.py** (Line 35)
   - From module: secrets
4. **models.py** (Line 5156)
   - From module: secrets
5. **models.py** (Line 5067)
   - From module: secrets
6. **serializers.py** (Line 30)
   - From module: secrets
7. **utils.py** (Line 7)
   - From module: secrets
8. **integration_system\auth_bridge.py** (Line 286)
   - From module: secrets
9. **management\commands\unlock_user_accounts.py** (Line 425)
   - From module: secrets

### selectors.DeviceInfoSelector

1. **interactors.py** (Line 18)
   - From module: selectors
2. **repositories.py** (Line 15)
   - From module: selectors
3. **use_cases.py** (Line 15)
   - From module: selectors

### selectors.SecurityIncidentSelector

1. **analytics.py** (Line 17)
   - From module: selectors
2. **data_export.py** (Line 20)
   - From module: selectors
3. **interactors.py** (Line 18)
   - From module: selectors
4. **repositories.py** (Line 15)
   - From module: selectors
5. **use_cases.py** (Line 15)
   - From module: selectors

### selectors.SecurityLogSelector

1. **analytics.py** (Line 17)
   - From module: selectors
2. **caching.py** (Line 439)
   - From module: selectors
3. **data_export.py** (Line 20)
   - From module: selectors
4. **interactors.py** (Line 18)
   - From module: selectors
5. **repositories.py** (Line 15)
   - From module: selectors
6. **use_cases.py** (Line 15)
   - From module: selectors

### selectors.ThreatIntelligenceSelector

1. **analytics.py** (Line 17)
   - From module: selectors
2. **data_export.py** (Line 20)
   - From module: selectors
3. **interactors.py** (Line 18)
   - From module: selectors
4. **repositories.py** (Line 15)
   - From module: selectors
5. **use_cases.py** (Line 15)
   - From module: selectors

### selectors.UserBanSelector

1. **interactors.py** (Line 18)
   - From module: selectors
2. **repositories.py** (Line 15)
   - From module: selectors
3. **use_cases.py** (Line 15)
   - From module: selectors

### serializers.DeviceInfoSerializer

1. **tests.py** (Line 1682)
   - From module: serializers
2. **tests.py** (Line 1392)
   - From module: serializers
3. **test_serializers.py** (Line 20)
   - From module: serializers
4. **views.py** (Line 74)
   - From module: serializers

### serializers.IPBlacklistSerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.PasswordHistorySerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.RiskScoreSerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.SecurityDashboardSerializer

1. **views.py** (Line 74)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.SecurityIncidentCreateSerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.SecurityIncidentSerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.SecurityInsightCreateSerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.SecurityInsightSerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.SecurityLogSerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.SecurityPolicyCreateSerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.SecurityPolicySerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.ThreatIntelligenceCreateSerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.ThreatIntelligenceSerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.TrustedDeviceCreateSerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.TrustedDeviceSerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.UserBanSerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### serializers.UserSessionSerializer

1. **test_serializers.py** (Line 20)
   - From module: serializers
2. **views.py** (Line 74)
   - From module: serializers

### smtplib

1. **dependencies.py** (Line 503)
   - From module: smtplib
2. **dependencies.py** (Line 554)
   - From module: smtplib

### string

1. **common_imports.py** (Line 12)
   - From module: string
2. **factories.py** (Line 7)
   - From module: string
3. **factories_backup.py** (Line 7)
   - From module: string
4. **models.py** (Line 36)
   - From module: string
5. **utils.py** (Line 8)
   - From module: string
6. **management\commands\unlock_user_accounts.py** (Line 426)
   - From module: string

### sys

1. **admin.py** (Line 2)
   - From module: sys
2. **common_imports.py** (Line 21)
   - From module: sys

### threading

1. **events.py** (Line 7)
   - From module: threading
2. **monitoring.py** (Line 8)
   - From module: threading
3. **signals_cap.py** (Line 7)
   - From module: threading
4. **tasks_cap.py** (Line 7)
   - From module: threading
5. **tests\test_threat_intel.py** (Line 825)
   - From module: threading
6. **tests\test_vpn_detector.py** (Line 710)
   - From module: threading

### time

1. **common_imports.py** (Line 17)
   - From module: time
2. **decorators.py** (Line 17)
   - From module: time
3. **monitoring.py** (Line 7)
   - From module: time
4. **serializers.py** (Line 1540)
   - From module: time
5. **tests.py** (Line 9)
   - From module: time
6. **tests.py** (Line 1687)
   - From module: time
7. **tests.py** (Line 2593)
   - From module: time
8. **tests.py** (Line 2639)
   - From module: time
9. **test_models.py** (Line 810)
   - From module: time
10. **test_serializers.py** (Line 803)
   - From module: time
11. **test_views.py** (Line 1050)
   - From module: time
12. **test_views.py** (Line 1079)
   - From module: time
13. **throttling.py** (Line 7)
   - From module: time
14. **views.py** (Line 8761)
   - From module: time
15. **integration_system\circuit_breaker.py** (Line 7)
   - From module: time
16. **integration_system\fallback_logic.py** (Line 7)
   - From module: time
17. **integration_system\health_check.py** (Line 7)
   - From module: time
18. **integration_system\message_queue.py** (Line 9)
   - From module: time
19. **integration_system\performance_monitor.py** (Line 7)
   - From module: time
20. **management\commands\run_security_scan.py** (Line 15)
   - From module: time
21. **tests\test_middleware.py** (Line 758)
   - From module: time
22. **tests\test_threat_intel.py** (Line 800)
   - From module: time
23. **tests\test_threat_intel.py** (Line 826)
   - From module: time
24. **tests\test_vpn_detector.py** (Line 711)
   - From module: time
25. **tests\test_vpn_detector.py** (Line 770)
   - From module: time
26. **utils\cache_manager.py** (Line 13)
   - From module: time

### traceback

1. **admin.py** (Line 3)
   - From module: traceback
2. **tasks.py** (Line 17)
   - From module: traceback
3. **utils\cache_manager.py** (Line 9)
   - From module: traceback

### typing.Any

1. **abstracts.py** (Line 8)
   - From module: typing
2. **admin.py** (Line 4)
   - From module: typing
3. **analytics.py** (Line 7)
   - From module: typing
4. **caching.py** (Line 10)
   - From module: typing
5. **common_imports.py** (Line 22)
   - From module: typing
6. **compliance.py** (Line 7)
   - From module: typing
7. **constants.py** (Line 7)
   - From module: typing
8. **consumers.py** (Line 16)
   - From module: typing
9. **context_processors.py** (Line 7)
   - From module: typing
10. **data_export.py** (Line 11)
   - From module: typing
11. **decorators.py** (Line 15)
   - From module: typing
12. **dependencies.py** (Line 11)
   - From module: typing
13. **encryption.py** (Line 10)
   - From module: typing
14. **endpoint.py** (Line 7)
   - From module: typing
15. **events.py** (Line 8)
   - From module: typing
16. **exceptions.py** (Line 11)
   - From module: typing
17. **feature_flags.py** (Line 7)
   - From module: typing
18. **hash_chain.py** (Line 10)
   - From module: typing
19. **hooks.py** (Line 7)
   - From module: typing
20. **interactors.py** (Line 7)
   - From module: typing
21. **logic.py** (Line 7)
   - From module: typing
22. **managers.py** (Line 12)
   - From module: typing
23. **mixins.py** (Line 18)
   - From module: typing
24. **models.py** (Line 27)
   - From module: typing
25. **models.py** (Line 47)
   - From module: typing
26. **model_mixins.py** (Line 8)
   - From module: typing
27. **monitoring.py** (Line 9)
   - From module: typing
28. **notifications_push.py** (Line 8)
   - From module: typing
29. **openai.py** (Line 11)
   - From module: typing
30. **pagination.py** (Line 7)
   - From module: typing
31. **plugins.py** (Line 8)
   - From module: typing
32. **querysets.py** (Line 7)
   - From module: typing
33. **receivers.py** (Line 15)
   - From module: typing
34. **registry.py** (Line 7)
   - From module: typing
35. **repositories.py** (Line 7)
   - From module: typing
36. **resources.py** (Line 7)
   - From module: typing
37. **sanctions.py** (Line 7)
   - From module: typing
38. **schemas.py** (Line 7)
   - From module: typing
39. **search.py** (Line 8)
   - From module: typing
40. **selectors.py** (Line 7)
   - From module: typing
41. **serializers.py** (Line 29)
   - From module: typing
42. **serializers.py** (Line 35)
   - From module: typing
43. **serializers.py** (Line 8708)
   - From module: typing
44. **services.py** (Line 13)
   - From module: typing
45. **signals.py** (Line 12)
   - From module: typing
46. **signals_cap.py** (Line 8)
   - From module: typing
47. **signals_kb.py** (Line 7)
   - From module: typing
48. **tasks_cap.py** (Line 8)
   - From module: typing
49. **tests.py** (Line 28)
   - From module: typing
50. **throttling.py** (Line 8)
   - From module: typing
51. **use_cases.py** (Line 7)
   - From module: typing
52. **utils.py** (Line 13)
   - From module: typing
53. **views.py** (Line 9)
   - From module: typing
54. **views.py** (Line 34)
   - From module: typing
55. **viewset.py** (Line 7)
   - From module: typing
56. **viewset_cap.py** (Line 7)
   - From module: typing
57. **webhooks.py** (Line 10)
   - From module: typing
58. **integration_system\auth_bridge.py** (Line 7)
   - From module: typing
59. **integration_system\bridge.py** (Line 8)
   - From module: typing
60. **integration_system\circuit_breaker.py** (Line 8)
   - From module: typing
61. **integration_system\data_bridge.py** (Line 8)
   - From module: typing
62. **integration_system\data_validator.py** (Line 8)
   - From module: typing
63. **integration_system\event_bus.py** (Line 9)
   - From module: typing
64. **integration_system\fallback_logic.py** (Line 8)
   - From module: typing
65. **integration_system\health_check.py** (Line 8)
   - From module: typing
66. **integration_system\integ_adapter.py** (Line 7)
   - From module: typing
67. **integration_system\integ_audit_logs.py** (Line 8)
   - From module: typing
68. **integration_system\integ_exceptions.py** (Line 7)
   - From module: typing
69. **integration_system\integ_handler.py** (Line 8)
   - From module: typing
70. **integration_system\integ_registry.py** (Line 7)
   - From module: typing
71. **integration_system\integ_signals.py** (Line 7)
   - From module: typing
72. **integration_system\message_queue.py** (Line 10)
   - From module: typing
73. **integration_system\performance_monitor.py** (Line 9)
   - From module: typing
74. **integration_system\sync_manager.py** (Line 7)
   - From module: typing
75. **integration_system\transformer.py** (Line 9)
   - From module: typing
76. **integration_system\versioning.py** (Line 7)
   - From module: typing
77. **integration_system\webhooks_integration.py** (Line 10)
   - From module: typing
78. **services\IncidentService.py** (Line 9)
   - From module: typing
79. **services\PasswordHistoryService.py** (Line 10)
   - From module: typing
80. **services\SecurityInsightService.py** (Line 10)
   - From module: typing
81. **services\SecurityPolicyService.py** (Line 10)
   - From module: typing
82. **services\ThreatIntelService.py** (Line 13)
   - From module: typing
83. **services\TrustedDeviceService.py** (Line 10)
   - From module: typing
84. **utils\cache_manager.py** (Line 6)
   - From module: typing
85. **utils\device.py** (Line 4)
   - From module: typing
86. **utils\security_helpers.py** (Line 10)
   - From module: typing
87. **utils\__init__.py** (Line 10)
   - From module: typing

### typing.Callable

1. **admin.py** (Line 4)
   - From module: typing
2. **caching.py** (Line 10)
   - From module: typing
3. **common_imports.py** (Line 22)
   - From module: typing
4. **decorators.py** (Line 15)
   - From module: typing
5. **endpoint.py** (Line 7)
   - From module: typing
6. **events.py** (Line 8)
   - From module: typing
7. **hooks.py** (Line 7)
   - From module: typing
8. **monitoring.py** (Line 9)
   - From module: typing
9. **plugins.py** (Line 8)
   - From module: typing
10. **registry.py** (Line 7)
   - From module: typing
11. **resources.py** (Line 7)
   - From module: typing
12. **signals_cap.py** (Line 8)
   - From module: typing
13. **signals_kb.py** (Line 7)
   - From module: typing
14. **tasks_cap.py** (Line 8)
   - From module: typing
15. **throttling.py** (Line 8)
   - From module: typing
16. **viewset_cap.py** (Line 7)
   - From module: typing
17. **webhooks.py** (Line 10)
   - From module: typing
18. **integration_system\auth_bridge.py** (Line 7)
   - From module: typing
19. **integration_system\bridge.py** (Line 8)
   - From module: typing
20. **integration_system\circuit_breaker.py** (Line 8)
   - From module: typing
21. **integration_system\data_bridge.py** (Line 8)
   - From module: typing
22. **integration_system\data_validator.py** (Line 8)
   - From module: typing
23. **integration_system\event_bus.py** (Line 9)
   - From module: typing
24. **integration_system\fallback_logic.py** (Line 8)
   - From module: typing
25. **integration_system\health_check.py** (Line 8)
   - From module: typing
26. **integration_system\integ_adapter.py** (Line 7)
   - From module: typing
27. **integration_system\integ_handler.py** (Line 8)
   - From module: typing
28. **integration_system\integ_registry.py** (Line 7)
   - From module: typing
29. **integration_system\integ_signals.py** (Line 7)
   - From module: typing
30. **integration_system\message_queue.py** (Line 10)
   - From module: typing
31. **integration_system\performance_monitor.py** (Line 9)
   - From module: typing
32. **integration_system\sync_manager.py** (Line 7)
   - From module: typing
33. **integration_system\transformer.py** (Line 9)
   - From module: typing
34. **integration_system\versioning.py** (Line 7)
   - From module: typing
35. **integration_system\webhooks_integration.py** (Line 10)
   - From module: typing
36. **utils\cache_manager.py** (Line 6)
   - From module: typing
37. **utils\device.py** (Line 4)
   - From module: typing

### typing.Dict

1. **abstracts.py** (Line 8)
   - From module: typing
2. **admin.py** (Line 4)
   - From module: typing
3. **analytics.py** (Line 7)
   - From module: typing
4. **caching.py** (Line 10)
   - From module: typing
5. **common_imports.py** (Line 22)
   - From module: typing
6. **compliance.py** (Line 7)
   - From module: typing
7. **constants.py** (Line 7)
   - From module: typing
8. **consumers.py** (Line 16)
   - From module: typing
9. **context_processors.py** (Line 7)
   - From module: typing
10. **data_export.py** (Line 11)
   - From module: typing
11. **decorators.py** (Line 15)
   - From module: typing
12. **dependencies.py** (Line 11)
   - From module: typing
13. **duplicate_analyzer.py** (Line 11)
   - From module: typing
14. **encryption.py** (Line 10)
   - From module: typing
15. **endpoint.py** (Line 7)
   - From module: typing
16. **events.py** (Line 8)
   - From module: typing
17. **exceptions.py** (Line 11)
   - From module: typing
18. **feature_flags.py** (Line 7)
   - From module: typing
19. **hash_chain.py** (Line 10)
   - From module: typing
20. **hooks.py** (Line 7)
   - From module: typing
21. **interactors.py** (Line 7)
   - From module: typing
22. **logic.py** (Line 7)
   - From module: typing
23. **managers.py** (Line 12)
   - From module: typing
24. **mixins.py** (Line 18)
   - From module: typing
25. **models.py** (Line 27)
   - From module: typing
26. **models.py** (Line 47)
   - From module: typing
27. **model_mixins.py** (Line 8)
   - From module: typing
28. **monitoring.py** (Line 9)
   - From module: typing
29. **notifications_push.py** (Line 8)
   - From module: typing
30. **openai.py** (Line 11)
   - From module: typing
31. **pagination.py** (Line 7)
   - From module: typing
32. **plugins.py** (Line 8)
   - From module: typing
33. **querysets.py** (Line 7)
   - From module: typing
34. **receivers.py** (Line 15)
   - From module: typing
35. **registry.py** (Line 7)
   - From module: typing
36. **repositories.py** (Line 7)
   - From module: typing
37. **resources.py** (Line 7)
   - From module: typing
38. **sanctions.py** (Line 7)
   - From module: typing
39. **schemas.py** (Line 7)
   - From module: typing
40. **search.py** (Line 8)
   - From module: typing
41. **selectors.py** (Line 7)
   - From module: typing
42. **serializers.py** (Line 29)
   - From module: typing
43. **serializers.py** (Line 35)
   - From module: typing
44. **serializers.py** (Line 8708)
   - From module: typing
45. **services.py** (Line 13)
   - From module: typing
46. **signals_cap.py** (Line 8)
   - From module: typing
47. **signals_kb.py** (Line 7)
   - From module: typing
48. **tasks_cap.py** (Line 8)
   - From module: typing
49. **tests.py** (Line 28)
   - From module: typing
50. **throttling.py** (Line 8)
   - From module: typing
51. **use_cases.py** (Line 7)
   - From module: typing
52. **utils.py** (Line 13)
   - From module: typing
53. **views.py** (Line 9)
   - From module: typing
54. **views.py** (Line 34)
   - From module: typing
55. **viewset.py** (Line 7)
   - From module: typing
56. **viewset_cap.py** (Line 7)
   - From module: typing
57. **webhooks.py** (Line 10)
   - From module: typing
58. **integration_system\auth_bridge.py** (Line 7)
   - From module: typing
59. **integration_system\bridge.py** (Line 8)
   - From module: typing
60. **integration_system\circuit_breaker.py** (Line 8)
   - From module: typing
61. **integration_system\data_bridge.py** (Line 8)
   - From module: typing
62. **integration_system\data_validator.py** (Line 8)
   - From module: typing
63. **integration_system\event_bus.py** (Line 9)
   - From module: typing
64. **integration_system\fallback_logic.py** (Line 8)
   - From module: typing
65. **integration_system\health_check.py** (Line 8)
   - From module: typing
66. **integration_system\integ_adapter.py** (Line 7)
   - From module: typing
67. **integration_system\integ_audit_logs.py** (Line 8)
   - From module: typing
68. **integration_system\integ_exceptions.py** (Line 7)
   - From module: typing
69. **integration_system\integ_handler.py** (Line 8)
   - From module: typing
70. **integration_system\integ_registry.py** (Line 7)
   - From module: typing
71. **integration_system\integ_signals.py** (Line 7)
   - From module: typing
72. **integration_system\message_queue.py** (Line 10)
   - From module: typing
73. **integration_system\performance_monitor.py** (Line 9)
   - From module: typing
74. **integration_system\sync_manager.py** (Line 7)
   - From module: typing
75. **integration_system\transformer.py** (Line 9)
   - From module: typing
76. **integration_system\versioning.py** (Line 7)
   - From module: typing
77. **integration_system\webhooks_integration.py** (Line 10)
   - From module: typing
78. **services\IncidentService.py** (Line 9)
   - From module: typing
79. **services\PasswordHistoryService.py** (Line 10)
   - From module: typing
80. **services\SecurityInsightService.py** (Line 10)
   - From module: typing
81. **services\SecurityPolicyService.py** (Line 10)
   - From module: typing
82. **services\ThreatIntelService.py** (Line 13)
   - From module: typing
83. **services\TrustedDeviceService.py** (Line 10)
   - From module: typing
84. **utils\cache_manager.py** (Line 6)
   - From module: typing
85. **utils\device.py** (Line 4)
   - From module: typing
86. **utils\security_helpers.py** (Line 10)
   - From module: typing
87. **utils\__init__.py** (Line 10)
   - From module: typing

### typing.List

1. **abstracts.py** (Line 8)
   - From module: typing
2. **admin.py** (Line 4)
   - From module: typing
3. **analytics.py** (Line 7)
   - From module: typing
4. **caching.py** (Line 10)
   - From module: typing
5. **choices.py** (Line 8)
   - From module: typing
6. **common_imports.py** (Line 22)
   - From module: typing
7. **compliance.py** (Line 7)
   - From module: typing
8. **constants.py** (Line 7)
   - From module: typing
9. **consumers.py** (Line 16)
   - From module: typing
10. **data_export.py** (Line 11)
   - From module: typing
11. **dependencies.py** (Line 11)
   - From module: typing
12. **duplicate_analyzer.py** (Line 11)
   - From module: typing
13. **encryption.py** (Line 10)
   - From module: typing
14. **endpoint.py** (Line 7)
   - From module: typing
15. **events.py** (Line 8)
   - From module: typing
16. **exceptions.py** (Line 11)
   - From module: typing
17. **feature_flags.py** (Line 7)
   - From module: typing
18. **hash_chain.py** (Line 10)
   - From module: typing
19. **hooks.py** (Line 7)
   - From module: typing
20. **interactors.py** (Line 7)
   - From module: typing
21. **logic.py** (Line 7)
   - From module: typing
22. **managers.py** (Line 12)
   - From module: typing
23. **mixins.py** (Line 18)
   - From module: typing
24. **models.py** (Line 27)
   - From module: typing
25. **models.py** (Line 47)
   - From module: typing
26. **model_mixins.py** (Line 8)
   - From module: typing
27. **monitoring.py** (Line 9)
   - From module: typing
28. **notifications_push.py** (Line 8)
   - From module: typing
29. **openai.py** (Line 11)
   - From module: typing
30. **pagination.py** (Line 7)
   - From module: typing
31. **permissions.py** (Line 12)
   - From module: typing
32. **permissions_backup.py** (Line 12)
   - From module: typing
33. **plugins.py** (Line 8)
   - From module: typing
34. **querysets.py** (Line 7)
   - From module: typing
35. **registry.py** (Line 7)
   - From module: typing
36. **repositories.py** (Line 7)
   - From module: typing
37. **resources.py** (Line 7)
   - From module: typing
38. **sanctions.py** (Line 7)
   - From module: typing
39. **schemas.py** (Line 7)
   - From module: typing
40. **search.py** (Line 8)
   - From module: typing
41. **selectors.py** (Line 7)
   - From module: typing
42. **serializers.py** (Line 29)
   - From module: typing
43. **serializers.py** (Line 35)
   - From module: typing
44. **serializers.py** (Line 8708)
   - From module: typing
45. **services.py** (Line 13)
   - From module: typing
46. **signals_cap.py** (Line 8)
   - From module: typing
47. **signals_kb.py** (Line 7)
   - From module: typing
48. **tasks_cap.py** (Line 8)
   - From module: typing
49. **tests.py** (Line 28)
   - From module: typing
50. **throttling.py** (Line 8)
   - From module: typing
51. **use_cases.py** (Line 7)
   - From module: typing
52. **utils.py** (Line 13)
   - From module: typing
53. **views.py** (Line 9)
   - From module: typing
54. **views.py** (Line 34)
   - From module: typing
55. **viewset.py** (Line 7)
   - From module: typing
56. **viewset_cap.py** (Line 7)
   - From module: typing
57. **webhooks.py** (Line 10)
   - From module: typing
58. **integration_system\auth_bridge.py** (Line 7)
   - From module: typing
59. **integration_system\bridge.py** (Line 8)
   - From module: typing
60. **integration_system\circuit_breaker.py** (Line 8)
   - From module: typing
61. **integration_system\data_bridge.py** (Line 8)
   - From module: typing
62. **integration_system\data_validator.py** (Line 8)
   - From module: typing
63. **integration_system\event_bus.py** (Line 9)
   - From module: typing
64. **integration_system\fallback_logic.py** (Line 8)
   - From module: typing
65. **integration_system\health_check.py** (Line 8)
   - From module: typing
66. **integration_system\integ_adapter.py** (Line 7)
   - From module: typing
67. **integration_system\integ_audit_logs.py** (Line 8)
   - From module: typing
68. **integration_system\integ_exceptions.py** (Line 7)
   - From module: typing
69. **integration_system\integ_handler.py** (Line 8)
   - From module: typing
70. **integration_system\integ_registry.py** (Line 7)
   - From module: typing
71. **integration_system\integ_signals.py** (Line 7)
   - From module: typing
72. **integration_system\message_queue.py** (Line 10)
   - From module: typing
73. **integration_system\performance_monitor.py** (Line 9)
   - From module: typing
74. **integration_system\sync_manager.py** (Line 7)
   - From module: typing
75. **integration_system\transformer.py** (Line 9)
   - From module: typing
76. **integration_system\versioning.py** (Line 7)
   - From module: typing
77. **integration_system\webhooks_integration.py** (Line 10)
   - From module: typing
78. **services\IncidentService.py** (Line 9)
   - From module: typing
79. **services\PasswordHistoryService.py** (Line 10)
   - From module: typing
80. **services\SecurityInsightService.py** (Line 10)
   - From module: typing
81. **services\SecurityPolicyService.py** (Line 10)
   - From module: typing
82. **services\ThreatIntelService.py** (Line 13)
   - From module: typing
83. **services\TrustedDeviceService.py** (Line 10)
   - From module: typing
84. **utils\cache_manager.py** (Line 6)
   - From module: typing
85. **utils\device.py** (Line 4)
   - From module: typing
86. **utils\security_helpers.py** (Line 10)
   - From module: typing

### typing.Optional

1. **abstracts.py** (Line 8)
   - From module: typing
2. **admin.py** (Line 4)
   - From module: typing
3. **analytics.py** (Line 7)
   - From module: typing
4. **caching.py** (Line 10)
   - From module: typing
5. **common_imports.py** (Line 22)
   - From module: typing
6. **compliance.py** (Line 7)
   - From module: typing
7. **consumers.py** (Line 16)
   - From module: typing
8. **context_processors.py** (Line 7)
   - From module: typing
9. **data_export.py** (Line 11)
   - From module: typing
10. **decorators.py** (Line 15)
   - From module: typing
11. **dependencies.py** (Line 11)
   - From module: typing
12. **encryption.py** (Line 10)
   - From module: typing
13. **endpoint.py** (Line 7)
   - From module: typing
14. **events.py** (Line 8)
   - From module: typing
15. **exceptions.py** (Line 11)
   - From module: typing
16. **feature_flags.py** (Line 7)
   - From module: typing
17. **hash_chain.py** (Line 10)
   - From module: typing
18. **hooks.py** (Line 7)
   - From module: typing
19. **interactors.py** (Line 7)
   - From module: typing
20. **logic.py** (Line 7)
   - From module: typing
21. **managers.py** (Line 12)
   - From module: typing
22. **mixins.py** (Line 18)
   - From module: typing
23. **models.py** (Line 23)
   - From module: typing
24. **models.py** (Line 27)
   - From module: typing
25. **models.py** (Line 47)
   - From module: typing
26. **model_mixins.py** (Line 8)
   - From module: typing
27. **monitoring.py** (Line 9)
   - From module: typing
28. **notifications_push.py** (Line 8)
   - From module: typing
29. **openai.py** (Line 11)
   - From module: typing
30. **pagination.py** (Line 7)
   - From module: typing
31. **permissions.py** (Line 12)
   - From module: typing
32. **permissions_backup.py** (Line 12)
   - From module: typing
33. **plugins.py** (Line 8)
   - From module: typing
34. **querysets.py** (Line 7)
   - From module: typing
35. **receivers.py** (Line 15)
   - From module: typing
36. **registry.py** (Line 7)
   - From module: typing
37. **repositories.py** (Line 7)
   - From module: typing
38. **resources.py** (Line 7)
   - From module: typing
39. **sanctions.py** (Line 7)
   - From module: typing
40. **schemas.py** (Line 7)
   - From module: typing
41. **search.py** (Line 8)
   - From module: typing
42. **selectors.py** (Line 7)
   - From module: typing
43. **serializers.py** (Line 29)
   - From module: typing
44. **serializers.py** (Line 35)
   - From module: typing
45. **serializers.py** (Line 8708)
   - From module: typing
46. **services.py** (Line 13)
   - From module: typing
47. **signals.py** (Line 12)
   - From module: typing
48. **signals_cap.py** (Line 8)
   - From module: typing
49. **signals_kb.py** (Line 7)
   - From module: typing
50. **tasks_cap.py** (Line 8)
   - From module: typing
51. **tests.py** (Line 28)
   - From module: typing
52. **throttling.py** (Line 8)
   - From module: typing
53. **use_cases.py** (Line 7)
   - From module: typing
54. **utils.py** (Line 13)
   - From module: typing
55. **views.py** (Line 9)
   - From module: typing
56. **views.py** (Line 34)
   - From module: typing
57. **viewset.py** (Line 7)
   - From module: typing
58. **viewset_cap.py** (Line 7)
   - From module: typing
59. **webhooks.py** (Line 10)
   - From module: typing
60. **integration_system\auth_bridge.py** (Line 7)
   - From module: typing
61. **integration_system\bridge.py** (Line 8)
   - From module: typing
62. **integration_system\circuit_breaker.py** (Line 8)
   - From module: typing
63. **integration_system\data_bridge.py** (Line 8)
   - From module: typing
64. **integration_system\data_validator.py** (Line 8)
   - From module: typing
65. **integration_system\event_bus.py** (Line 9)
   - From module: typing
66. **integration_system\fallback_logic.py** (Line 8)
   - From module: typing
67. **integration_system\health_check.py** (Line 8)
   - From module: typing
68. **integration_system\integ_adapter.py** (Line 7)
   - From module: typing
69. **integration_system\integ_audit_logs.py** (Line 8)
   - From module: typing
70. **integration_system\integ_exceptions.py** (Line 7)
   - From module: typing
71. **integration_system\integ_handler.py** (Line 8)
   - From module: typing
72. **integration_system\integ_registry.py** (Line 7)
   - From module: typing
73. **integration_system\integ_signals.py** (Line 7)
   - From module: typing
74. **integration_system\message_queue.py** (Line 10)
   - From module: typing
75. **integration_system\performance_monitor.py** (Line 9)
   - From module: typing
76. **integration_system\sync_manager.py** (Line 7)
   - From module: typing
77. **integration_system\transformer.py** (Line 9)
   - From module: typing
78. **integration_system\versioning.py** (Line 7)
   - From module: typing
79. **integration_system\webhooks_integration.py** (Line 10)
   - From module: typing
80. **services\IncidentService.py** (Line 9)
   - From module: typing
81. **services\PasswordHistoryService.py** (Line 10)
   - From module: typing
82. **services\SecurityInsightService.py** (Line 10)
   - From module: typing
83. **services\SecurityPolicyService.py** (Line 10)
   - From module: typing
84. **services\ThreatIntelService.py** (Line 13)
   - From module: typing
85. **services\TrustedDeviceService.py** (Line 10)
   - From module: typing
86. **utils\cache_manager.py** (Line 6)
   - From module: typing
87. **utils\device.py** (Line 4)
   - From module: typing
88. **utils\security_helpers.py** (Line 10)
   - From module: typing

### typing.Tuple

1. **admin.py** (Line 4)
   - From module: typing
2. **choices.py** (Line 8)
   - From module: typing
3. **common_imports.py** (Line 22)
   - From module: typing
4. **duplicate_analyzer.py** (Line 11)
   - From module: typing
5. **encryption.py** (Line 10)
   - From module: typing
6. **managers.py** (Line 12)
   - From module: typing
7. **models.py** (Line 23)
   - From module: typing
8. **models.py** (Line 47)
   - From module: typing
9. **search.py** (Line 8)
   - From module: typing
10. **serializers.py** (Line 35)
   - From module: typing
11. **serializers.py** (Line 8708)
   - From module: typing
12. **services.py** (Line 13)
   - From module: typing
13. **utils.py** (Line 13)
   - From module: typing
14. **views.py** (Line 9)
   - From module: typing
15. **services\IncidentService.py** (Line 9)
   - From module: typing
16. **services\PasswordHistoryService.py** (Line 10)
   - From module: typing
17. **services\SecurityPolicyService.py** (Line 10)
   - From module: typing
18. **services\ThreatIntelService.py** (Line 13)
   - From module: typing
19. **utils\cache_manager.py** (Line 6)
   - From module: typing
20. **utils\device.py** (Line 4)
   - From module: typing
21. **utils\security_helpers.py** (Line 10)
   - From module: typing

### typing.Type

1. **abstracts.py** (Line 8)
   - From module: typing
2. **admin.py** (Line 4)
   - From module: typing
3. **analytics.py** (Line 7)
   - From module: typing
4. **caching.py** (Line 10)
   - From module: typing
5. **compliance.py** (Line 7)
   - From module: typing
6. **data_export.py** (Line 11)
   - From module: typing
7. **encryption.py** (Line 10)
   - From module: typing
8. **endpoint.py** (Line 7)
   - From module: typing
9. **events.py** (Line 8)
   - From module: typing
10. **feature_flags.py** (Line 7)
   - From module: typing
11. **hooks.py** (Line 7)
   - From module: typing
12. **interactors.py** (Line 7)
   - From module: typing
13. **logic.py** (Line 7)
   - From module: typing
14. **monitoring.py** (Line 9)
   - From module: typing
15. **notifications_push.py** (Line 8)
   - From module: typing
16. **pagination.py** (Line 7)
   - From module: typing
17. **plugins.py** (Line 8)
   - From module: typing
18. **querysets.py** (Line 7)
   - From module: typing
19. **registry.py** (Line 7)
   - From module: typing
20. **repositories.py** (Line 7)
   - From module: typing
21. **resources.py** (Line 7)
   - From module: typing
22. **sanctions.py** (Line 7)
   - From module: typing
23. **schemas.py** (Line 7)
   - From module: typing
24. **search.py** (Line 8)
   - From module: typing
25. **selectors.py** (Line 7)
   - From module: typing
26. **signals_cap.py** (Line 8)
   - From module: typing
27. **tasks_cap.py** (Line 8)
   - From module: typing
28. **use_cases.py** (Line 7)
   - From module: typing
29. **viewset.py** (Line 7)
   - From module: typing
30. **viewset_cap.py** (Line 7)
   - From module: typing
31. **integration_system\auth_bridge.py** (Line 7)
   - From module: typing
32. **integration_system\bridge.py** (Line 8)
   - From module: typing
33. **integration_system\circuit_breaker.py** (Line 8)
   - From module: typing
34. **integration_system\data_bridge.py** (Line 8)
   - From module: typing
35. **integration_system\data_validator.py** (Line 8)
   - From module: typing
36. **integration_system\event_bus.py** (Line 9)
   - From module: typing
37. **integration_system\fallback_logic.py** (Line 8)
   - From module: typing
38. **integration_system\health_check.py** (Line 8)
   - From module: typing
39. **integration_system\integ_adapter.py** (Line 7)
   - From module: typing
40. **integration_system\integ_audit_logs.py** (Line 8)
   - From module: typing
41. **integration_system\integ_exceptions.py** (Line 7)
   - From module: typing
42. **integration_system\integ_handler.py** (Line 8)
   - From module: typing
43. **integration_system\integ_registry.py** (Line 7)
   - From module: typing
44. **integration_system\integ_signals.py** (Line 7)
   - From module: typing
45. **integration_system\message_queue.py** (Line 10)
   - From module: typing
46. **integration_system\performance_monitor.py** (Line 9)
   - From module: typing
47. **integration_system\sync_manager.py** (Line 7)
   - From module: typing
48. **integration_system\transformer.py** (Line 9)
   - From module: typing
49. **integration_system\versioning.py** (Line 7)
   - From module: typing
50. **integration_system\webhooks_integration.py** (Line 10)
   - From module: typing

### typing.Union

1. **abstracts.py** (Line 8)
   - From module: typing
2. **admin.py** (Line 4)
   - From module: typing
3. **analytics.py** (Line 7)
   - From module: typing
4. **caching.py** (Line 10)
   - From module: typing
5. **common_imports.py** (Line 22)
   - From module: typing
6. **compliance.py** (Line 7)
   - From module: typing
7. **data_export.py** (Line 11)
   - From module: typing
8. **decorators.py** (Line 15)
   - From module: typing
9. **dependencies.py** (Line 11)
   - From module: typing
10. **encryption.py** (Line 10)
   - From module: typing
11. **endpoint.py** (Line 7)
   - From module: typing
12. **events.py** (Line 8)
   - From module: typing
13. **feature_flags.py** (Line 7)
   - From module: typing
14. **hooks.py** (Line 7)
   - From module: typing
15. **interactors.py** (Line 7)
   - From module: typing
16. **logic.py** (Line 7)
   - From module: typing
17. **models.py** (Line 47)
   - From module: typing
18. **monitoring.py** (Line 9)
   - From module: typing
19. **notifications_push.py** (Line 8)
   - From module: typing
20. **openai.py** (Line 11)
   - From module: typing
21. **permissions.py** (Line 12)
   - From module: typing
22. **permissions_backup.py** (Line 12)
   - From module: typing
23. **plugins.py** (Line 8)
   - From module: typing
24. **querysets.py** (Line 7)
   - From module: typing
25. **repositories.py** (Line 7)
   - From module: typing
26. **resources.py** (Line 7)
   - From module: typing
27. **sanctions.py** (Line 7)
   - From module: typing
28. **schemas.py** (Line 7)
   - From module: typing
29. **search.py** (Line 8)
   - From module: typing
30. **selectors.py** (Line 7)
   - From module: typing
31. **serializers.py** (Line 35)
   - From module: typing
32. **serializers.py** (Line 8708)
   - From module: typing
33. **signals_cap.py** (Line 8)
   - From module: typing
34. **tasks_cap.py** (Line 8)
   - From module: typing
35. **throttling.py** (Line 8)
   - From module: typing
36. **use_cases.py** (Line 7)
   - From module: typing
37. **utils.py** (Line 13)
   - From module: typing
38. **viewset.py** (Line 7)
   - From module: typing
39. **integration_system\auth_bridge.py** (Line 7)
   - From module: typing
40. **integration_system\bridge.py** (Line 8)
   - From module: typing
41. **integration_system\circuit_breaker.py** (Line 8)
   - From module: typing
42. **integration_system\data_bridge.py** (Line 8)
   - From module: typing
43. **integration_system\data_validator.py** (Line 8)
   - From module: typing
44. **integration_system\event_bus.py** (Line 9)
   - From module: typing
45. **integration_system\fallback_logic.py** (Line 8)
   - From module: typing
46. **integration_system\health_check.py** (Line 8)
   - From module: typing
47. **integration_system\integ_adapter.py** (Line 7)
   - From module: typing
48. **integration_system\integ_audit_logs.py** (Line 8)
   - From module: typing
49. **integration_system\integ_exceptions.py** (Line 7)
   - From module: typing
50. **integration_system\integ_handler.py** (Line 8)
   - From module: typing
51. **integration_system\integ_registry.py** (Line 7)
   - From module: typing
52. **integration_system\integ_signals.py** (Line 7)
   - From module: typing
53. **integration_system\message_queue.py** (Line 10)
   - From module: typing
54. **integration_system\performance_monitor.py** (Line 9)
   - From module: typing
55. **integration_system\sync_manager.py** (Line 7)
   - From module: typing
56. **integration_system\transformer.py** (Line 9)
   - From module: typing
57. **integration_system\versioning.py** (Line 7)
   - From module: typing
58. **integration_system\webhooks_integration.py** (Line 10)
   - From module: typing
59. **utils\cache_manager.py** (Line 6)
   - From module: typing

### unittest.mock.MagicMock

1. **common_imports.py** (Line 118)
   - From module: unittest.mock
2. **tests.py** (Line 11)
   - From module: unittest.mock
3. **test_models.py** (Line 11)
   - From module: unittest.mock
4. **test_serializers.py** (Line 13)
   - From module: unittest.mock
5. **test_views.py** (Line 13)
   - From module: unittest.mock
6. **tests\test_incident_service.py** (Line 9)
   - From module: unittest.mock
7. **tests\test_middleware.py** (Line 9)
   - From module: unittest.mock
8. **tests\test_password_policy.py** (Line 9)
   - From module: unittest.mock
9. **tests\test_security_insight.py** (Line 9)
   - From module: unittest.mock
10. **tests\test_security_models.py** (Line 17)
   - From module: unittest.mock
11. **tests\test_security_policy.py** (Line 9)
   - From module: unittest.mock
12. **tests\test_security_views.py** (Line 9)
   - From module: unittest.mock
13. **tests\test_threat_intel.py** (Line 9)
   - From module: unittest.mock
14. **tests\test_trusted_device.py** (Line 9)
   - From module: unittest.mock
15. **tests\test_vpn_detector.py** (Line 9)
   - From module: unittest.mock

### unittest.mock.patch

1. **common_imports.py** (Line 118)
   - From module: unittest.mock
2. **tests.py** (Line 11)
   - From module: unittest.mock
3. **test_models.py** (Line 11)
   - From module: unittest.mock
4. **test_serializers.py** (Line 13)
   - From module: unittest.mock
5. **test_views.py** (Line 13)
   - From module: unittest.mock
6. **tests\test_incident_service.py** (Line 9)
   - From module: unittest.mock
7. **tests\test_middleware.py** (Line 9)
   - From module: unittest.mock
8. **tests\test_password_policy.py** (Line 9)
   - From module: unittest.mock
9. **tests\test_security_insight.py** (Line 9)
   - From module: unittest.mock
10. **tests\test_security_models.py** (Line 17)
   - From module: unittest.mock
11. **tests\test_security_policy.py** (Line 9)
   - From module: unittest.mock
12. **tests\test_security_views.py** (Line 9)
   - From module: unittest.mock
13. **tests\test_threat_intel.py** (Line 9)
   - From module: unittest.mock
14. **tests\test_trusted_device.py** (Line 9)
   - From module: unittest.mock
15. **tests\test_vpn_detector.py** (Line 9)
   - From module: unittest.mock

### urllib.parse.urlparse

1. **common_imports.py** (Line 125)
   - From module: urllib.parse
2. **models.py** (Line 42)
   - From module: urllib.parse

### utils.RateLimiter

1. **mixins.py** (Line 20)
   - From module: utils
2. **receivers.py** (Line 22)
   - From module: utils

### utils.SecurityUtils

1. **abstracts.py** (Line 14)
   - From module: utils
2. **analytics.py** (Line 18)
   - From module: utils
3. **caching.py** (Line 19)
   - From module: utils
4. **common_imports.py** (Line 153)
   - From module: utils
5. **compliance.py** (Line 16)
   - From module: utils
6. **context_processors.py** (Line 13)
   - From module: utils
7. **data_export.py** (Line 21)
   - From module: utils
8. **encryption.py** (Line 24)
   - From module: utils
9. **endpoint.py** (Line 22)
   - From module: utils
10. **events.py** (Line 18)
   - From module: utils
11. **feature_flags.py** (Line 15)
   - From module: utils
12. **forms.py** (Line 13)
   - From module: utils
13. **hooks.py** (Line 16)
   - From module: utils
14. **interactors.py** (Line 22)
   - From module: utils
15. **logic.py** (Line 15)
   - From module: utils
16. **mixins.py** (Line 20)
   - From module: utils
17. **monitoring.py** (Line 19)
   - From module: utils
18. **notifications_push.py** (Line 17)
   - From module: utils
19. **plugins.py** (Line 15)
   - From module: utils
20. **querysets.py** (Line 15)
   - From module: utils
21. **receivers.py** (Line 22)
   - From module: utils
22. **resources.py** (Line 16)
   - From module: utils
23. **sanctions.py** (Line 17)
   - From module: utils
24. **schemas.py** (Line 12)
   - From module: utils
25. **search.py** (Line 17)
   - From module: utils
26. **signals_cap.py** (Line 18)
   - From module: utils
27. **signals_kb.py** (Line 17)
   - From module: utils
28. **tasks_cap.py** (Line 20)
   - From module: utils
29. **test_models.py** (Line 19)
   - From module: utils
30. **throttling.py** (Line 18)
   - From module: utils
31. **use_cases.py** (Line 19)
   - From module: utils
32. **webhooks.py** (Line 23)
   - From module: utils
33. **integration_system\auth_bridge.py** (Line 18)
   - From module: utils
34. **integration_system\bridge.py** (Line 17)
   - From module: utils
35. **integration_system\circuit_breaker.py** (Line 17)
   - From module: utils
36. **integration_system\data_bridge.py** (Line 17)
   - From module: utils
37. **integration_system\data_validator.py** (Line 18)
   - From module: utils
38. **integration_system\event_bus.py** (Line 18)
   - From module: utils
39. **integration_system\fallback_logic.py** (Line 17)
   - From module: utils
40. **integration_system\health_check.py** (Line 17)
   - From module: utils
41. **integration_system\integ_adapter.py** (Line 16)
   - From module: utils
42. **integration_system\integ_audit_logs.py** (Line 17)
   - From module: utils
43. **integration_system\integ_handler.py** (Line 17)
   - From module: utils
44. **integration_system\integ_registry.py** (Line 16)
   - From module: utils
45. **integration_system\integ_signals.py** (Line 17)
   - From module: utils
46. **integration_system\message_queue.py** (Line 19)
   - From module: utils
47. **integration_system\performance_monitor.py** (Line 18)
   - From module: utils
48. **integration_system\sync_manager.py** (Line 16)
   - From module: utils
49. **integration_system\transformer.py** (Line 18)
   - From module: utils
50. **integration_system\versioning.py** (Line 16)
   - From module: utils
51. **integration_system\webhooks_integration.py** (Line 26)
   - From module: utils

### uuid

1. **attachment_upload_view.py** (Line 9)
   - From module: uuid
2. **common_imports.py** (Line 10)
   - From module: uuid
3. **models.py** (Line 31)
   - From module: uuid
4. **serializers.py** (Line 1645)
   - From module: uuid
5. **tests.py** (Line 381)
   - From module: uuid
6. **migrations\0001_initial.py** (Line 6)
   - From module: uuid
7. **migrations\0005_add_threat_intelligence_and_security_incident.py** (Line 9)
   - From module: uuid
8. **tests\factories.py** (Line 8)
   - From module: uuid
9. **tests\test_security_models.py** (Line 8)
   - From module: uuid

## 🔍 Detailed Analysis

### 🚨 Most Problematic Duplicates

- **Class:** Meta (193 occurrences)
- **Function:** __init__ (352 occurrences)

## 💡 Recommendations

### 🏷️ For Duplicate Classes:
1. **Merge similar classes** - If classes have similar functionality, consider merging
2. **Use inheritance** - Create a base class and inherit from it
3. **Rename classes** - Use more specific names to avoid conflicts
4. **Move to modules** - Separate classes into different modules

### 🔧 For Duplicate Functions:
1. **Create utility modules** - Move common functions to utility modules
2. **Use mixins** - Create mixin classes for shared functionality
3. **Rename functions** - Use more descriptive names
4. **Consolidate logic** - Merge functions with similar logic

### 📦 For Duplicate Imports:
1. **Create import modules** - Consolidate imports in __init__.py files
2. **Remove unused imports** - Clean up unnecessary imports
3. **Use absolute imports** - Standardize import style

