import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

const IMAGE_URL = (import.meta as any).env.VITE_IMAGE_URL || 'http://localhost:8001';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getImageUrl(item: any): string {
  if (!item) return 'https://placehold.co/400x400?text=No+Image';
  
  const path = item.local_path || item.image_link || item.image_url || item.path || (typeof item === 'string' ? item : '');
  
  if (!path) return 'https://placehold.co/400x400?text=No+Image';
  if (path.startsWith('http')) return path;
  if (path.startsWith('data:')) return path;
  
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${IMAGE_URL}${cleanPath}`;
}
