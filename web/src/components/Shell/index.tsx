import { NoteComposeModal } from "../NoteComposeModal";
import { ProjectModal } from "../ProjectModal";
import { ResumeUploadModal } from "../ResumeUploadModal";
import { DrillMaterialModal } from "../DrillMaterialModal";
import { Sidebar } from "../Sidebar";
import { SegmentedTabs } from "../SegmentedTabs";
import { Toast } from "../Toast";
import { ViewNoteModal } from "../ViewNoteModal";
import { useStore } from "../../store";
import { ExaminePage } from "../../pages/ExaminePage";
import { TeachPage } from "../../pages/TeachPage";
import { DrillPage } from "../../pages/DrillPage";
import styles from "./index.module.scss";

export function Shell() {
  const { mode, setMode, notes, error, flash } = useStore();

  const examineCount = notes.filter((n) => n.claim_ids.length > 0).length;

  return (
    <div className={styles.shell}>
      <Sidebar />

      <main className={styles.main}>
        <div className={styles.mainHead}>
          <SegmentedTabs mode={mode} onChange={setMode} examineCount={examineCount} />
        </div>

        {mode === "examine" ? <ExaminePage /> : null}
        {mode === "teach" ? <TeachPage /> : null}
        {mode === "drill" ? <DrillPage /> : null}
      </main>

      <Toast error={error} flash={flash} />

      <NoteComposeModal />
      <ViewNoteModal />
      <ProjectModal />
      <ResumeUploadModal />
      <DrillMaterialModal />
    </div>
  );
}
