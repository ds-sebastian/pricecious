import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { useSettings } from "@/hooks/use-settings";
import { ChevronDown, ChevronUp, Cpu } from "lucide-react";
import React, { useState } from "react";

export function AIConfig() {
	const { settings, updateSetting } = useSettings();
	const [showAdvancedAI, setShowAdvancedAI] = useState(false);

	const ai_provider = settings.ai_provider || "ollama";
	const ai_model = settings.ai_model || "moondream";
	const ai_api_key = settings.ai_api_key || "";
	const ai_api_base =
		settings.ai_api_base !== undefined
			? settings.ai_api_base
			: "http://ollama:11434";
	const ai_temperature = Number.parseFloat(settings.ai_temperature || "0.1");
	const ai_max_tokens = Number.parseInt(settings.ai_max_tokens || "300");
	const ai_reasoning_effort = settings.ai_reasoning_effort || "low";

	const confidence_threshold_price = Number.parseFloat(
		settings.confidence_threshold_price || "0.5",
	);
	const confidence_threshold_stock = Number.parseFloat(
		settings.confidence_threshold_stock || "0.5",
	);


	const price_outlier_threshold_enabled =
		settings.price_outlier_threshold_enabled === "true";
	const price_outlier_threshold_percent = Number.parseFloat(
		settings.price_outlier_threshold_percent || "500",
	);

	return (
		<Card>
			<CardHeader>
				<CardTitle className="flex items-center gap-2">
					<Cpu className="h-5 w-5" />
					AI Configuration
				</CardTitle>
				<CardDescription>
					Configure the AI model used for analyzing product pages.
				</CardDescription>
			</CardHeader>
			<CardContent className="space-y-6">
				<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
					<div className="space-y-2">
						<Label>Provider</Label>
						<Select
							value={ai_provider}
							onValueChange={(val) => updateSetting("ai_provider", val)}
						>
							<SelectTrigger>
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="ollama">Ollama</SelectItem>
								<SelectItem value="openai">OpenAI</SelectItem>
								<SelectItem value="anthropic">Anthropic</SelectItem>
								<SelectItem value="openrouter">OpenRouter</SelectItem>
							</SelectContent>
						</Select>
					</div>
					<div className="space-y-2">
						<Label>Model</Label>
						<Input
							value={ai_model}
							onChange={(e) => updateSetting("ai_model", e.target.value)}
							placeholder="e.g., moondream"
						/>
					</div>
				</div>
				<div className="space-y-2">
					<Label>API Key</Label>
					<Input
						type="password"
						value={ai_api_key}
						onChange={(e) => updateSetting("ai_api_key", e.target.value)}
						placeholder="Optional for local models"
					/>
				</div>

				<div className="pt-2">
					<Button
						variant="outline"
						size="sm"
						className="w-full flex items-center justify-between"
						onClick={() => setShowAdvancedAI(!showAdvancedAI)}
					>
						<span>Advanced Settings</span>
						{showAdvancedAI ? (
							<ChevronUp className="h-4 w-4" />
						) : (
							<ChevronDown className="h-4 w-4" />
						)}
					</Button>
				</div>

				{showAdvancedAI && (
					<div className="space-y-6 pt-4 animate-in slide-in-from-top-2 duration-200">
						<div className="space-y-2">
							<Label>API Base URL</Label>
							<Input
								value={ai_api_base}
								onChange={(e) => updateSetting("ai_api_base", e.target.value)}
							/>
						</div>

						<div className="grid grid-cols-1 md:grid-cols-2 gap-8">
							<div className="space-y-4">
								<div className="space-y-2">
									<div className="flex justify-between">
										<Label>Temperature</Label>
										<span className="text-xs text-muted-foreground">
											{ai_temperature}
										</span>
									</div>
									<Slider
										min={0}
										max={1}
										step={0.1}
										value={[ai_temperature]}
										onValueChange={(vals) =>
											updateSetting("ai_temperature", vals[0])
										}
									/>
								</div>
								<div className="space-y-2">
									<Label>Reasoning Effort</Label>
									<Select
										value={ai_reasoning_effort}
										onValueChange={(val) =>
											updateSetting("ai_reasoning_effort", val)
										}
									>
										<SelectTrigger>
											<SelectValue />
										</SelectTrigger>
										<SelectContent>
											<SelectItem value="minimal">Minimal (Fastest)</SelectItem>
											<SelectItem value="low">Low (Faster/Cheaper)</SelectItem>
											<SelectItem value="medium">Medium</SelectItem>
											<SelectItem value="high">High (More Thorough)</SelectItem>
										</SelectContent>
									</Select>
									<p className="text-xs text-muted-foreground">
										Only for supported models (e.g. gpt-5, gpt-5.1, o1). Use
										"minimal" for fastest/cheapest responses.
									</p>
								</div>
								<div className="space-y-2">
									<div className="flex justify-between">
										<Label>Price Confidence Threshold</Label>
										<span className="text-xs text-muted-foreground">
											{confidence_threshold_price}
										</span>
									</div>
									<Slider
										min={0}
										max={1}
										step={0.1}
										value={[confidence_threshold_price]}
										onValueChange={(vals) =>
											updateSetting("confidence_threshold_price", vals[0])
										}
									/>
								</div>
								<div className="space-y-2">
									<div className="flex justify-between">
										<Label>Stock Confidence Threshold</Label>
										<span className="text-xs text-muted-foreground">
											{confidence_threshold_stock}
										</span>
									</div>
									<Slider
										min={0}
										max={1}
										step={0.1}
										value={[confidence_threshold_stock]}
										onValueChange={(vals) =>
											updateSetting("confidence_threshold_stock", vals[0])
										}
									/>
								</div>
								<div className="space-y-4 pt-4 border-t">
									<div className="flex items-center justify-between">
										<Label htmlFor="outlier_enabled">
											Price Outlier Protection
										</Label>
										<Switch
											id="outlier_enabled"
											checked={price_outlier_threshold_enabled}
											onCheckedChange={(checked) =>
												updateSetting(
													"price_outlier_threshold_enabled",
													checked,
												)
											}
										/>
									</div>
									{price_outlier_threshold_enabled && (
										<div className="space-y-2">
											<div className="flex justify-between">
												<Label>Outlier Threshold (%)</Label>
												<span className="text-xs text-muted-foreground">
													{price_outlier_threshold_percent}%
												</span>
											</div>
											<Input
												type="number"
												value={price_outlier_threshold_percent}
												onChange={(e) =>
													updateSetting(
														"price_outlier_threshold_percent",
														Number.parseFloat(e.target.value),
													)
												}
											/>
											<p className="text-xs text-muted-foreground">
												Reject price increases larger than this percentage.
											</p>
										</div>
									)}
								</div>
							</div>

							<div className="space-y-4">
								<div className="space-y-2">
									<Label>Max Tokens</Label>
									<Input
										type="number"
										value={ai_max_tokens}
										onChange={(e) =>
											updateSetting(
												"ai_max_tokens",
												Number.parseInt(e.target.value),
											)
										}
									/>
								</div>

							</div>
						</div>
					</div>
				)}
			</CardContent>
		</Card>
	);
}
