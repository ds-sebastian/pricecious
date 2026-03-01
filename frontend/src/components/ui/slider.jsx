import React from "react";
import { cn } from "@/lib/utils";

const Slider = React.forwardRef(({ className, ...props }, ref) => (
	<input
		type="range"
		className={cn(
			"w-full h-2 bg-zinc-200 rounded-lg appearance-none cursor-pointer dark:bg-zinc-700 accent-primary",
			className,
		)}
		ref={ref}
		{...props}
	/>
));
Slider.displayName = "Slider";

export { Slider };
