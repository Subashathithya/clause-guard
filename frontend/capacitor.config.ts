import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.clauseguard.app',
  appName: 'ClauseGuard',
  webDir: 'build',
  server: {
    androidScheme: 'https'
  }
};

export default config;
