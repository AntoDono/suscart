import KnotapiJS from 'knotapi-js';

// Knot API Authentication and Transaction Sync
const KNOT_CLIENT_ID = 'dda0778d-9486-47f8-bd80-6f2512f9bcdb';
const KNOT_SECRET = 'ff5e51b6dcf84a829898d37449cbc47a';
const KNOT_API_URL = 'https://development.knotapi.com';

// Create Basic Auth header
const getAuthHeader = () => {
  const credentials = `${KNOT_CLIENT_ID}:${KNOT_SECRET}`;
  return `Basic ${btoa(credentials)}`;
};

export interface KnotSession {
  session_token: string;
  url: string;
}

/**
 * Create a Knot session for user authentication
 */
export const createKnotSession = async (externalUserId: string, merchantId?: number): Promise<KnotSession> => {
  try {
    const body: any = {
      type: 'transaction_link', // Required: type of Knot product
      external_user_id: externalUserId, // Changed from client_user_id
    };

    // Optionally specify merchant to connect to
    if (merchantId) {
      body.merchant_id = merchantId;
    }

    const response = await fetch(`${KNOT_API_URL}/session/create`, {
      method: 'POST',
      headers: {
        'Authorization': getAuthHeader(),
        'Content-Type': 'application/json',
        'Knot-Version': '2.0'
      },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const error = await response.text();
      console.error('Knot session creation failed:', response.status, error);
      throw new Error(`Failed to create Knot session: ${response.status}`);
    }

    const data = await response.json();
    console.log('✅ Knot session created:', data);
    console.log('Session object keys:', Object.keys(data));
    console.log('Session value:', data.session);
    console.log('Has url?', data.url);

    // If API returns URL, use it
    if (data.url) {
      console.log('Using API-provided URL:', data.url);
      return {
        session_token: data.session || data.session_token,
        url: data.url
      };
    }

    // Otherwise construct URL from session token
    // Try /connect/{session} instead of /session/{session}
    const sessionUrl = `${KNOT_API_URL}/connect/${data.session}`;
    console.log('Constructed URL:', sessionUrl);

    return {
      session_token: data.session,
      url: sessionUrl
    };
  } catch (error) {
    console.error('❌ Error creating Knot session:', error);
    throw error;
  }
};

/**
 * Sync transactions for a user from a specific merchant
 */
export const syncKnotTransactions = async (
  externalUserId: string,
  merchantId: number,
  cursor?: string,
  limit: number = 20
) => {
  try {
    const body: any = {
      merchant_id: merchantId,
      external_user_id: externalUserId,
      limit
    };

    if (cursor) {
      body.cursor = cursor;
    }

    console.log('Syncing Knot transactions:', body);

    const response = await fetch(`${KNOT_API_URL}/transactions/sync`, {
      method: 'POST',
      headers: {
        'Authorization': getAuthHeader(),
        'Content-Type': 'application/json',
        'Knot-Version': '2.0'
      },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const error = await response.text();
      console.error('Knot transaction sync failed:', response.status, error);
      throw new Error(`Failed to sync transactions: ${response.status}`);
    }

    const data = await response.json();
    console.log('✅ Knot transactions synced:', data);
    return data;
  } catch (error) {
    console.error('❌ Error syncing Knot transactions:', error);
    throw error;
  }
};

/**
 * Open Knot authentication modal using the official SDK
 * Returns merchant ID on success, or null on failure
 */
export const openKnotAuthModal = (sessionToken: string): Promise<{ success: boolean; merchantId?: number }> => {
  return new Promise((resolve) => {
    console.log('Initializing Knot SDK with session:', sessionToken);

    const knotapi = new KnotapiJS();
    let connectedMerchantId: number | undefined;

    knotapi.open({
      sessionId: sessionToken,
      clientId: KNOT_CLIENT_ID,
      environment: 'development',
      product: 'transaction_link',
      // Don't specify merchantIds - let user choose any merchant
      entryPoint: 'edgecart_portal',
      useCategories: true,
      useSearch: true,

      onSuccess: (product: string, details: any) => {
        console.log('✅ Knot onSuccess:', product, details);
        resolve({ success: true, merchantId: connectedMerchantId });
      },

      onError: (product: string, errorCode: string, message: string) => {
        console.error('❌ Knot onError:', product, errorCode, message);
        resolve({ success: false });
      },

      onExit: (product: string) => {
        console.log('User closed Knot SDK:', product);
        resolve({ success: false });
      },

      onEvent: (_product: string, event: string, merchant: string, merchantId: string, _payload?: any, _taskId?: string) => {
        console.log('Knot event:', event, merchant, merchantId);

        // Capture merchant ID when user authenticates
        if (event === 'AUTHENTICATED') {
          console.log('✅ User authenticated with merchant:', merchant, 'ID:', merchantId);
          connectedMerchantId = parseInt(merchantId);
        }
      }
    });
  });
};

// Add fadeIn animation
const style = document.createElement('style');
style.textContent = `
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
`;
document.head.appendChild(style);

// Merchant IDs from Knot
export const MERCHANTS = {
  AMAZON: 44,
  COSTCO: 165,
  DOORDASH: 19,
  INSTACART: 40,
  TARGET: 12,
  UBEREATS: 36,
  WALMART: 45
} as const;
