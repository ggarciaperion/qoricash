import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_CONFIG, STORAGE_KEYS } from '../constants/config';

class ApiClient {
  private client: AxiosInstance;
  private sessionCookie: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_CONFIG.BASE_URL,
      timeout: API_CONFIG.TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
      },
      withCredentials: true, // Important for session cookies
    });

    // Request interceptor to add session cookie
    this.client.interceptors.request.use(
      async (config) => {
        if (this.sessionCookie) {
          config.headers.Cookie = this.sessionCookie;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor to handle session cookies
    this.client.interceptors.response.use(
      (response) => {
        // Extract and store session cookie
        const setCookie = response.headers['set-cookie'];
        if (setCookie && setCookie.length > 0) {
          this.sessionCookie = setCookie[0];
        }
        return response;
      },
      async (error) => {
        // Handle 401 Unauthorized
        if (error.response?.status === 401) {
          await this.clearSession();
          // You can emit an event here to redirect to login
        }
        return Promise.reject(error);
      }
    );
  }

  async setSessionCookie(cookie: string) {
    this.sessionCookie = cookie;
    await AsyncStorage.setItem(STORAGE_KEYS.AUTH_TOKEN, cookie);
  }

  async loadSessionCookie() {
    const cookie = await AsyncStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
    if (cookie) {
      this.sessionCookie = cookie;
    }
  }

  async clearSession() {
    this.sessionCookie = null;
    await AsyncStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
    await AsyncStorage.removeItem(STORAGE_KEYS.USER_DATA);
    await AsyncStorage.removeItem(STORAGE_KEYS.CLIENT_DATA);
  }

  // Generic HTTP methods
  async get<T = any>(url: string, config?: AxiosRequestConfig) {
    const response = await this.client.get<T>(url, config);
    return response.data;
  }

  async post<T = any>(url: string, data?: any, config?: AxiosRequestConfig) {
    const response = await this.client.post<T>(url, data, config);
    return response.data;
  }

  async put<T = any>(url: string, data?: any, config?: AxiosRequestConfig) {
    const response = await this.client.put<T>(url, data, config);
    return response.data;
  }

  async patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig) {
    const response = await this.client.patch<T>(url, data, config);
    return response.data;
  }

  async delete<T = any>(url: string, config?: AxiosRequestConfig) {
    const response = await this.client.delete<T>(url, config);
    return response.data;
  }

  // Upload file method
  async uploadFile<T = any>(url: string, formData: FormData) {
    const response = await this.client.post<T>(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  // Special method for form-based login that expects HTML response
  async loginWithForm(username: string, password: string) {
    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const response = await this.client.post('/login', formData.toString(), {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        maxRedirects: 0, // Don't follow redirects
        validateStatus: (status) => status >= 200 && status < 400, // Accept redirects as success
      });

      // Extract session cookie from response
      const setCookie = response.headers['set-cookie'];
      if (setCookie && setCookie.length > 0) {
        await this.setSessionCookie(setCookie[0]);
      }

      // Check if login was successful by looking at redirect or response
      const isSuccess = response.status === 302 || response.status === 200;

      return {
        success: isSuccess,
        headers: response.headers,
        status: response.status,
      };
    } catch (error: any) {
      // Handle redirect as success (302 Found)
      if (error.response?.status === 302) {
        const setCookie = error.response.headers['set-cookie'];
        if (setCookie && setCookie.length > 0) {
          await this.setSessionCookie(setCookie[0]);
        }
        return {
          success: true,
          headers: error.response.headers,
          status: 302,
        };
      }
      throw error;
    }
  }
}

export default new ApiClient();
