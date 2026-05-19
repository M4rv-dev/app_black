import { useState, useEffect } from 'react';
import { globalIsConnected, addGlobalConnectionStateListener } from './useWebSocket';

/**
 * Lightweight hook that subscribes to the global WebSocket connection state
 * without affecting the connection lifecycle.
 * Safe to use in any component — does not open or close the WebSocket.
 */
export function useWsStatus(): { isConnected: boolean } {
  const [isConnected, setIsConnected] = useState(globalIsConnected);

  useEffect(() => {
    setIsConnected(globalIsConnected);
    return addGlobalConnectionStateListener(setIsConnected);
  }, []);

  return { isConnected };
}
