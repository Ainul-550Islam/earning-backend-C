// src/api/endpoints/index.js
import * as UserEndpoints from './users';
import * as WalletEndpoints from './wallet';
import * as TaskEndpoints from './tasks';
import * as SecurityEndpoints from './security';
import * as FraudEndpoints from './fraudDetection';
import * as AnalyticsEndpoints from './analytics';

export {
  UserEndpoints,
  WalletEndpoints,
  TaskEndpoints,
  SecurityEndpoints,
  FraudEndpoints,
  AnalyticsEndpoints
};