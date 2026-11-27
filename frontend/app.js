import { segmentsPage } from "./pages/segments.js";
import { trialsPage } from "./pages/trials.js";
import { blindPage } from "./pages/blind.js";
import { movesPage } from "./pages/moves.js";
import { handoverPage } from "./pages/handover.js";

export default {
  title: "汀线",
  subtitle: "海滩铺毯与通行交接",
  pages: [
    {id: "segments", title: "分段示意", render: segmentsPage},
    {id: "trials", title: "通行试验", render: root => trialsPage(root)},
    {id: "blind", title: "模型盲测", render: root => blindPage(root)},
    {id: "moves", title: "换段推演", render: root => movesPage(root)},
    {id: "handover", title: "值班交接", render: root => handoverPage(root)},
  ],
};
