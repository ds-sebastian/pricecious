import axios from "axios";

export const API_URL = "/api";

// Shared API functions for React Query

export const fetchItems = () =>
    axios.get(`${API_URL}/items`).then((r) => r.data);

export const fetchAnalytics = (itemId, { days, stdDevThreshold }) => {
    let url = `${API_URL}/items/${itemId}/analytics?days=${days}`;
    if (stdDevThreshold) {
        url += `&std_dev_threshold=${stdDevThreshold}`;
    }
    return axios.get(url).then((r) => r.data);
};

// Query key factories for consistent cache management
export const queryKeys = {
    analytics: (itemId, params) => ["analytics", itemId, params],
};

export const testNotificationProfile = (appriseUrl) =>
    axios
        .post(`${API_URL}/notification-profiles/test`, { apprise_url: appriseUrl })
        .then((r) => r.data);
