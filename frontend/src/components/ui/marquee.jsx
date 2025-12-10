import { cn } from "@/lib/utils";
import React, { useEffect, useRef, useState } from "react";

export function Marquee({ text, className }) {
	const [isOverflowing, setIsOverflowing] = useState(false);
	const containerRef = useRef(null);
	const textRef = useRef(null);

	// biome-ignore lint/correctness/useExhaustiveDependencies: text is needed to trigger recalculation
	useEffect(() => {
		const checkOverflow = () => {
			if (containerRef.current && textRef.current) {
				const isOver =
					textRef.current.scrollWidth > containerRef.current.clientWidth;
				setIsOverflowing(isOver);
				if (isOver) {
					const distance = textRef.current.scrollWidth + 32; // 32px gap
					containerRef.current.style.setProperty(
						"--marquee-duration",
						`${distance / 40}s`,
					); // 40px/s speed
					containerRef.current.style.setProperty(
						"--marquee-distance",
						`${distance}px`,
					);
				}
			}
		};

		checkOverflow();
		window.addEventListener("resize", checkOverflow);
		return () => window.removeEventListener("resize", checkOverflow);
	}, [text]);

	return (
		<div
			ref={containerRef}
			className={cn("overflow-hidden w-full group", className)}
		>
			<div
				ref={textRef}
				className={cn(
					"whitespace-nowrap flex gap-8",
					isOverflowing && "group-hover:animate-scroll",
				)}
			>
				<span>{text}</span>
				{isOverflowing && <span aria-hidden="true">{text}</span>}
			</div>
		</div>
	);
}
