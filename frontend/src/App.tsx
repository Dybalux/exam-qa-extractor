import { useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { Layout, PageHead, ButtonLink } from './components.tsx'
import Dashboard from './pages/Dashboard.tsx'
import PracticeStart from './pages/PracticeStart.tsx'
import PracticeQuestion from './pages/PracticeQuestion.tsx'
import PracticeResults from './pages/PracticeResults.tsx'
import ExamList from './pages/ExamList.tsx'
import ExamForm from './pages/ExamForm.tsx'
import ExamDetail from './pages/ExamDetail.tsx'
import BulkUpload from './pages/BulkUpload.tsx'
import QuestionList from './pages/QuestionList.tsx'
import QuestionDetail from './pages/QuestionDetail.tsx'
import QuestionManualForm from './pages/QuestionManualForm.tsx'
import QuestionCorrect from './pages/QuestionCorrect.tsx'
import ReviewQueue from './pages/ReviewQueue.tsx'
import AnswerForm from './pages/AnswerForm.tsx'
import AnswerManage from './pages/AnswerManage.tsx'
import Analytics from './pages/Analytics.tsx'
import WeakAreas from './pages/WeakAreas.tsx'

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

function NotFound() {
  return (
    <div className="stack">
      <PageHead title="Página no encontrada" lead="Esa dirección todavía no existe en la nueva aplicación." />
      <div className="row">
        <ButtonLink to="/">Ir al dashboard</ButtonLink>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <>
      <ScrollToTop />
      <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="practice" element={<PracticeStart />} />
        <Route path="practice/:sessionId" element={<PracticeQuestion />} />
        <Route path="practice/:sessionId/results" element={<PracticeResults />} />
        <Route path="exams" element={<ExamList />} />
        <Route path="exams/new" element={<ExamForm />} />
        <Route path="exams/:examId" element={<ExamDetail />} />
        <Route path="exams/:examId/edit" element={<ExamForm />} />
        <Route path="exams/:examId/upload" element={<BulkUpload />} />
        <Route path="exams/:examId/questions/new" element={<QuestionManualForm />} />
        <Route path="questions" element={<QuestionList />} />
        <Route path="questions/review" element={<ReviewQueue />} />
        <Route path="questions/:questionId" element={<QuestionDetail />} />
        <Route path="questions/:questionId/correct" element={<QuestionCorrect />} />
        <Route path="questions/:questionId/answers/new" element={<AnswerForm />} />
        <Route path="questions/:questionId/answers/manage" element={<AnswerManage />} />
        <Route path="questions/:questionId/answers/:answerId/edit" element={<AnswerForm />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="analytics/weak-areas" element={<WeakAreas />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
    </>
  )
}
