import patrick from "../../assets/avatars/patrick.png";
import sandy from "../../assets/avatars/sandy.png";
import spongebob from "../../assets/avatars/spongebob.png";
import squidward from "../../assets/avatars/squidward.png";

function AvatarImg({ src, alt }: { src: string; alt: string }) {
  return (
    <img
      src={src}
      alt={alt}
      style={{
        width: "100%",
        height: "100%",
        objectFit: "cover",
        display: "block",
      }}
    />
  );
}

export function SquidwardAvatar() {
  return <AvatarImg src={squidward} alt="章鱼哥" />;
}

export function SpongeBobAvatar() {
  return <AvatarImg src={spongebob} alt="海绵宝宝" />;
}

export function PatrickAvatar() {
  return <AvatarImg src={patrick} alt="派大星" />;
}

export function SandyAvatar() {
  return <AvatarImg src={sandy} alt="桑迪" />;
}
