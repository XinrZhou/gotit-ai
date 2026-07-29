/** Local learner profile (name + avatar) for Settings / nav rail. */

export type UserProfile = {
  name: string;
  /** data URL or empty for initials avatar */
  avatar: string;
};

const KEY = "gotit.userProfile";
const DEFAULT_NAME = "学习者";

export function loadUserProfile(): UserProfile {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { name: DEFAULT_NAME, avatar: "" };
    const parsed = JSON.parse(raw) as Partial<UserProfile>;
    return {
      name: (parsed.name?.trim() || DEFAULT_NAME).slice(0, 32),
      avatar: typeof parsed.avatar === "string" ? parsed.avatar : "",
    };
  } catch {
    return { name: DEFAULT_NAME, avatar: "" };
  }
}

export function saveUserProfile(profile: UserProfile): void {
  const next: UserProfile = {
    name: (profile.name.trim() || DEFAULT_NAME).slice(0, 32),
    avatar: profile.avatar.slice(0, 600_000),
  };
  localStorage.setItem(KEY, JSON.stringify(next));
}

export function profileInitials(name: string): string {
  const t = name.trim();
  if (!t) return "?";
  // CJK: first char; Latin: up to 2 initials
  if (/[\u4e00-\u9fff]/.test(t[0])) return t.slice(0, 1);
  const parts = t.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return t.slice(0, 2).toUpperCase();
}

/** Soft fill from name — quiet, not loud accent. */
export function profileTint(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i += 1) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  const hues = [210, 160, 30, 280, 190];
  const hue = hues[h % hues.length];
  return `hsl(${hue} 18% 88%)`;
}

export async function fileToAvatarDataUrl(file: File): Promise<string> {
  if (!file.type.startsWith("image/")) {
    throw new Error("请选择图片文件");
  }
  if (file.size > 1.5 * 1024 * 1024) {
    throw new Error("头像请小于 1.5MB");
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const url = String(reader.result || "");
      // Downscale via canvas for storage budget
      const img = new Image();
      img.onload = () => {
        const size = 128;
        const canvas = document.createElement("canvas");
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          resolve(url);
          return;
        }
        const min = Math.min(img.width, img.height);
        const sx = (img.width - min) / 2;
        const sy = (img.height - min) / 2;
        ctx.drawImage(img, sx, sy, min, min, 0, 0, size, size);
        resolve(canvas.toDataURL("image/jpeg", 0.85));
      };
      img.onerror = () => reject(new Error("无法读取图片"));
      img.src = url;
    };
    reader.onerror = () => reject(new Error("无法读取文件"));
    reader.readAsDataURL(file);
  });
}
