import { API_URL } from "@/lib/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { toast } from "sonner";

export function useSettings() {
	const queryClient = useQueryClient();

	const { data: settings = {}, isLoading } = useQuery({
		queryKey: ["settings"],
		queryFn: async () => {
			const response = await axios.get(`${API_URL}/settings`);
			const settingsMap = {};
			response.data.forEach((s) => (settingsMap[s.key] = s.value));
			return settingsMap;
		},
	});

	const updateSettingMutation = useMutation({
		mutationFn: async ({ key, value }) => {
			await axios.post(`${API_URL}/settings`, { key, value: value.toString() });
		},
		onSuccess: (_, { key, value }) => {
			queryClient.setQueryData(["settings"], (old) => ({
				...old,
				[key]: value.toString(),
			}));
			toast.success("Setting updated");
		},
		onError: () => {
			toast.error("Failed to update setting");
		},
	});

	return {
		settings,
		isLoading,
		updateSetting: (key, value) => updateSettingMutation.mutate({ key, value }),
	};
}
