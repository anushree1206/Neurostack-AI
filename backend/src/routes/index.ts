import { Router, type IRouter } from "express";
import healthRouter from "./health";
import apiRouter from "./api";

const router: IRouter = Router();

router.use(healthRouter);
router.use(apiRouter);

export default router;
