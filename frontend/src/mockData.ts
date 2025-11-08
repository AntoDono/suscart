// Mock data for demo profiles when backend is unavailable
export const mockCustomers = {
  'abc': {
    id: 1,
    knot_customer_id: 'abc',
    name: 'Sarah Chen',
    email: 'sarah@example.com',
    preferences: {
      favorite_fruits: ['Strawberry', 'Blueberry', 'Spinach'],
      favorite_products: ['Organic Berries', 'Fresh Greens'],
      average_spend: 45.50,
      merchants_used: ['Whole Foods', 'Trader Joe\'s'],
      total_transactions: 24,
      max_price: 100,
      preferred_discount: 15
    }
  },
  'def': {
    id: 2,
    knot_customer_id: 'def',
    name: 'Marcus Lee',
    email: 'marcus@example.com',
    preferences: {
      favorite_fruits: ['Orange', 'Grapefruit', 'Kale'],
      favorite_products: ['Citrus Fruits', 'Leafy Greens'],
      average_spend: 52.30,
      merchants_used: ['Whole Foods', 'Sprouts'],
      total_transactions: 31,
      max_price: 120,
      preferred_discount: 20
    }
  },
  'ghi': {
    id: 3,
    knot_customer_id: 'ghi',
    name: 'Emily Rodriguez',
    email: 'emily@example.com',
    preferences: {
      favorite_fruits: ['Grape', 'Dragon Fruit', 'Kiwi'],
      favorite_products: ['Exotic Fruits', 'Organic Produce'],
      average_spend: 68.90,
      merchants_used: ['Whole Foods', 'Asian Market', 'Farmers Market'],
      total_transactions: 42,
      max_price: 150,
      preferred_discount: 25
    }
  }
};

export const mockRecommendations = {
  'abc': [
    {
      id: 1,
      inventory_id: 101,
      priority_score: 95,
      sent_at: new Date().toISOString(),
      viewed: false,
      purchased: false,
      item: {
        id: 101,
        fruit_type: 'Strawberry',
        variety: 'Organic',
        quantity: 15,
        original_price: 6.99,
        current_price: 4.99,
        discount_percentage: 28,
        freshness: {
          freshness_score: 85,
          status: 'fresh',
          predicted_expiry_date: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString()
        }
      },
      reason: {
        match_type: 'favorite_fruit',
        fruit: 'Strawberry',
        reasoning: 'Fresh organic strawberries just arrived! We know you love berries.',
        discount: 28
      }
    },
    {
      id: 2,
      inventory_id: 102,
      priority_score: 88,
      sent_at: new Date().toISOString(),
      viewed: false,
      purchased: false,
      item: {
        id: 102,
        fruit_type: 'Blueberry',
        variety: 'Wild',
        quantity: 20,
        original_price: 8.99,
        current_price: 6.49,
        discount_percentage: 28,
        freshness: {
          freshness_score: 78,
          status: 'fresh',
          predicted_expiry_date: new Date(Date.now() + 4 * 24 * 60 * 60 * 1000).toISOString()
        }
      },
      reason: {
        match_type: 'favorite_fruit',
        fruit: 'Blueberry',
        reasoning: 'Wild blueberries on sale - perfect for your morning smoothies!',
        discount: 28
      }
    }
  ],
  'def': [
    {
      id: 3,
      inventory_id: 201,
      priority_score: 92,
      sent_at: new Date().toISOString(),
      viewed: false,
      purchased: false,
      item: {
        id: 201,
        fruit_type: 'Orange',
        variety: 'Valencia',
        quantity: 30,
        original_price: 5.99,
        current_price: 3.99,
        discount_percentage: 33,
        freshness: {
          freshness_score: 90,
          status: 'fresh',
          predicted_expiry_date: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString()
        }
      },
      reason: {
        match_type: 'favorite_fruit',
        fruit: 'Orange',
        reasoning: 'Sweet Valencia oranges perfect for your fitness routine!',
        discount: 33
      }
    },
    {
      id: 4,
      inventory_id: 202,
      priority_score: 87,
      sent_at: new Date().toISOString(),
      viewed: false,
      purchased: false,
      item: {
        id: 202,
        fruit_type: 'Grapefruit',
        variety: 'Ruby Red',
        quantity: 18,
        original_price: 7.49,
        current_price: 4.99,
        discount_percentage: 33,
        freshness: {
          freshness_score: 82,
          status: 'fresh',
          predicted_expiry_date: new Date(Date.now() + 4 * 24 * 60 * 60 * 1000).toISOString()
        }
      },
      reason: {
        match_type: 'favorite_fruit',
        fruit: 'Grapefruit',
        reasoning: 'Ruby red grapefruit - tangy and refreshing for your smoothies!',
        discount: 33
      }
    }
  ],
  'ghi': [
    {
      id: 5,
      inventory_id: 301,
      priority_score: 96,
      sent_at: new Date().toISOString(),
      viewed: false,
      purchased: false,
      item: {
        id: 301,
        fruit_type: 'Dragon Fruit',
        variety: 'White',
        quantity: 12,
        original_price: 12.99,
        current_price: 8.99,
        discount_percentage: 31,
        freshness: {
          freshness_score: 88,
          status: 'fresh',
          predicted_expiry_date: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString()
        }
      },
      reason: {
        match_type: 'favorite_fruit',
        fruit: 'Dragon Fruit',
        reasoning: 'Exotic white dragon fruit - rare find at this price!',
        discount: 31
      }
    },
    {
      id: 6,
      inventory_id: 302,
      priority_score: 90,
      sent_at: new Date().toISOString(),
      viewed: false,
      purchased: false,
      item: {
        id: 302,
        fruit_type: 'Kiwi',
        variety: 'Golden',
        quantity: 25,
        original_price: 9.99,
        current_price: 6.99,
        discount_percentage: 30,
        freshness: {
          freshness_score: 85,
          status: 'fresh',
          predicted_expiry_date: new Date(Date.now() + 6 * 24 * 60 * 60 * 1000).toISOString()
        }
      },
      reason: {
        match_type: 'favorite_fruit',
        fruit: 'Kiwi',
        reasoning: 'Golden kiwis - sweeter and less tart than green!',
        discount: 30
      }
    },
    {
      id: 7,
      inventory_id: 303,
      priority_score: 85,
      sent_at: new Date().toISOString(),
      viewed: false,
      purchased: false,
      item: {
        id: 303,
        fruit_type: 'Grape',
        variety: 'Cotton Candy',
        quantity: 22,
        original_price: 8.99,
        current_price: 5.99,
        discount_percentage: 33,
        freshness: {
          freshness_score: 92,
          status: 'fresh',
          predicted_expiry_date: new Date(Date.now() + 4 * 24 * 60 * 60 * 1000).toISOString()
        }
      },
      reason: {
        match_type: 'favorite_fruit',
        fruit: 'Grape',
        reasoning: 'Cotton candy grapes - taste like actual cotton candy!',
        discount: 33
      }
    }
  ]
};

export const mockPurchases = {
  'abc': [
    {
      id: 1,
      inventory_id: 99,
      quantity: 2,
      price_paid: 8.99,
      discount_applied: 25,
      purchase_date: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
      knot_transaction_id: null,
      fruit_type: 'Strawberry'
    }
  ],
  'def': [
    {
      id: 2,
      inventory_id: 98,
      quantity: 3,
      price_paid: 11.99,
      discount_applied: 30,
      purchase_date: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
      knot_transaction_id: null,
      fruit_type: 'Orange'
    }
  ],
  'ghi': [
    {
      id: 3,
      inventory_id: 97,
      quantity: 1,
      price_paid: 9.99,
      discount_applied: 35,
      purchase_date: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
      knot_transaction_id: null,
      fruit_type: 'Dragon Fruit'
    }
  ]
};

export const mockKnotTransactions = {
  'abc': [
    {
      id: 'knot_tx_1',
      external_id: 'abc_order_123',
      datetime: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      url: 'https://example.com/order/123',
      order_status: 'delivered',
      price: {
        sub_total: '42.50',
        total: '45.99',
        currency: 'USD'
      },
      products: [
        {
          external_id: 'prod_1',
          name: 'Organic Strawberries',
          quantity: 2,
          price: {
            sub_total: '13.98',
            total: '13.98',
            unit_price: '6.99'
          }
        },
        {
          external_id: 'prod_2',
          name: 'Fresh Blueberries',
          quantity: 3,
          price: {
            sub_total: '26.97',
            total: '26.97',
            unit_price: '8.99'
          }
        }
      ]
    }
  ],
  'def': [
    {
      id: 'knot_tx_2',
      external_id: 'def_order_456',
      datetime: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(),
      url: 'https://example.com/order/456',
      order_status: 'delivered',
      price: {
        sub_total: '38.75',
        total: '41.50',
        currency: 'USD'
      },
      products: [
        {
          external_id: 'prod_3',
          name: 'Valencia Oranges',
          quantity: 5,
          price: {
            sub_total: '29.95',
            total: '29.95',
            unit_price: '5.99'
          }
        },
        {
          external_id: 'prod_4',
          name: 'Kale Bunch',
          quantity: 2,
          price: {
            sub_total: '7.98',
            total: '7.98',
            unit_price: '3.99'
          }
        }
      ]
    }
  ],
  'ghi': [
    {
      id: 'knot_tx_3',
      external_id: 'ghi_order_789',
      datetime: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
      url: 'https://example.com/order/789',
      order_status: 'delivered',
      price: {
        sub_total: '55.80',
        total: '59.99',
        currency: 'USD'
      },
      products: [
        {
          external_id: 'prod_5',
          name: 'Dragon Fruit',
          quantity: 2,
          price: {
            sub_total: '25.98',
            total: '25.98',
            unit_price: '12.99'
          }
        },
        {
          external_id: 'prod_6',
          name: 'Golden Kiwi',
          quantity: 3,
          price: {
            sub_total: '29.97',
            total: '29.97',
            unit_price: '9.99'
          }
        }
      ]
    }
  ]
};
