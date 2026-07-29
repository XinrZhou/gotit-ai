import { NoteComposeModal } from "../NoteComposeModal";
import { ProjectModal } from "../ProjectModal";
import { ResumeUploadModal } from "../ResumeUploadModal";
import { ResumeViewerModal } from "../ResumeViewerModal";
import { DrillMaterialModal } from "../DrillMaterialModal";
import { Sidebar } from "../Sidebar";
import { Toast } from "../Toast";
import { ViewNoteModal } from "../ViewNoteModal";
import { useStore } from "../../store";
import { ChatPage } from "../../pages/ChatPage";
import { SettingsPage } from "../../pages/SettingsPage";
import styles from "./index.module.scss";

export function Shell() {
  const { error, flash, libraryOpen, setLibraryOpen } = useStore();

  return (
    <div className={styles.shell}>
      <div
        className={`${styles.library} ${libraryOpen ? styles.libraryOpen : ""}`}
        aria-hidden={!libraryOpen}
      >
        <div className={styles.libraryInner}>
          <Sidebar />
        </div>
      </div>

      {libraryOpen ? (
        <button
          type="button"
          className={styles.libraryScrim}
          aria-label="关闭资料栏"
          onClick={() => setLibraryOpen(false)}
        />
      ) : null}

      <main className={styles.main}>
        <ChatPage />
      </main>

      <Toast error={error} flash={flash} />

      <NoteComposeModal />
      <ViewNoteModal />
      <ProjectModal />
      <ResumeUploadModal />
      <ResumeViewerModal />
      <DrillMaterialModal />
      <SettingsPage />
    </div>
  );
}
