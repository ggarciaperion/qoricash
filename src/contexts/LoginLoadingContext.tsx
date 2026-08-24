import React, { createContext, useState, useContext, ReactNode } from 'react';

interface LoginLoadingContextData {
  showLoginLoading: boolean;
  setShowLoginLoading: (show: boolean) => void;
  showLogoutLoading: boolean;
  setShowLogoutLoading: (show: boolean) => void;
}

const LoginLoadingContext = createContext<LoginLoadingContextData>({
  showLoginLoading: false,
  setShowLoginLoading: () => {},
  showLogoutLoading: false,
  setShowLogoutLoading: () => {},
});

export const LoginLoadingProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [showLoginLoading, setShowLoginLoading]   = useState(false);
  const [showLogoutLoading, setShowLogoutLoading] = useState(false);

  return (
    <LoginLoadingContext.Provider value={{
      showLoginLoading, setShowLoginLoading,
      showLogoutLoading, setShowLogoutLoading,
    }}>
      {children}
    </LoginLoadingContext.Provider>
  );
};

export const useLoginLoading = () => {
  const context = useContext(LoginLoadingContext);
  if (!context) {
    throw new Error('useLoginLoading must be used within LoginLoadingProvider');
  }
  return context;
};
