const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function fetchPrivateBlob(path) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('admin_access_token') : '';
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: 'no-store',
  });
  if (!response.ok) {
    throw new Error('Could not load file');
  }
  return URL.createObjectURL(await response.blob());
}
