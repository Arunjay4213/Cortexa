"use client";

import Link from "next/link";

interface EntityLinkProps {
  type: "memory" | "agent" | "transaction" | "contradiction";
  id: string;
  truncate?: number;
  className?: string;
}

function getHref(type: EntityLinkProps["type"], id: string): string {
  switch (type) {
    case "memory":
      return `/memories?selected=${id}`;
    case "agent":
      return `/fleet?selected=${id}`;
    case "transaction":
      return `/attribution?selected=${id}`;
    case "contradiction":
      return "/health";
  }
}

export function EntityLink({
  type,
  id,
  truncate = 8,
  className = "",
}: EntityLinkProps) {
  const href = getHref(type, id);
  const displayId = id.length > truncate ? id.slice(0, truncate) + "..." : id;

  return (
    <Link
      href={href}
      title={id}
      className={`inline-flex items-center font-mono text-[var(--accent)] hover:text-[var(--accent-hover)] hover:underline transition-colors ${className}`}
    >
      {displayId}
    </Link>
  );
}
