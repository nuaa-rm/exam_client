interface LoginRes {
  success: boolean;
  error?: string;
}

interface Alert {
    id: string;
    text: string;
}

interface PyWebviewApi {
  login: (uname: string, password: string, endpoint: string) => Promise<LoginRes>;
  getAlerts: () => Promise<Alert[] | null>;
  getAvailableDevices: () => Promise<{ monitors: { [key: number]: string }; cameras: { [key: number]: string } }>;
  startScreenRecorder: (monitor_idx: number, monitor_name: string) => Promise<boolean>;
  startCameraRecorder: (camera_idx: number, camera_name: string) => Promise<boolean>;
  captureHealth: () => Promise<boolean>;
  getEndpoint: () => Promise<string | null>;
  gotoExam: () => Promise<void>;
}

declare global {
  interface Window {
    pywebview?: {
      api: PyWebviewApi;
    };
  }
}

export {};
