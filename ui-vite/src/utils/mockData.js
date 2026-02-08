// src/utils/mockData.js

export const assessmentQuestions = [
  {
    id: 1,
    question: 'Bạn thích làm việc với loại dữ liệu nào nhất?',
    options: [
      { text: 'Số liệu và thống kê', value: 'data' },
      { text: 'Hình ảnh và thiết kế', value: 'visual' },
      { text: 'Văn bản và nội dung', value: 'text' },
      { text: 'Code và logic', value: 'code' }
    ]
  },
  {
    id: 2,
    question: 'Môi trường làm việc lý tưởng của bạn là?',
    options: [
      { text: 'Văn phòng công ty lớn', value: 'corporate' },
      { text: 'Startup năng động', value: 'startup' },
      { text: 'Làm việc từ xa', value: 'remote' },
      { text: 'Freelance tự do', value: 'freelance' }
    ]
  },
  {
    id: 3,
    question: 'Bạn thích học hỏi qua hình thức nào?',
    options: [
      { text: 'Khóa học có cấu trúc', value: 'structured' },
      { text: 'Tự học và nghiên cứu', value: 'self-study' },
      { text: 'Thực hành dự án thực tế', value: 'hands-on' },
      { text: 'Học từ mentor', value: 'mentorship' }
    ]
  },
  {
    id: 4,
    question: 'Điểm mạnh nhất của bạn là gì?',
    options: [
      { text: 'Tư duy logic và giải quyết vấn đề', value: 'logical' },
      { text: 'Sáng tạo và thẩm mỹ', value: 'creative' },
      { text: 'Giao tiếp và làm việc nhóm', value: 'communication' },
      { text: 'Phân tích và chiến lược', value: 'analytical' }
    ]
  },
  {
    id: 5,
    question: 'Bạn quan tâm đến lĩnh vực nào nhất?',
    options: [
      { text: 'Trí tuệ nhân tạo & Machine Learning', value: 'ai' },
      { text: 'Phát triển phần mềm', value: 'software' },
      { text: 'Thiết kế & UX', value: 'design' },
      { text: 'Kinh doanh & Marketing', value: 'business' }
    ]
  }
];

export const mockCareerRecommendations = [
  {
    id: 'ai-engineer',
    name: 'AI Engineer',
    icon: '🤖',
    domain: 'AI',
    description: 'Kỹ sư AI chuyên phát triển các hệ thống trí tuệ nhân tạo, machine learning và deep learning. Làm việc với dữ liệu lớn để xây dựng các mô hình AI giải quyết vấn đề thực tế.',
    matchScore: 0.95,
    growthRate: 0.92,
    competition: 0.85,
    aiRelevance: 0.98,
    requiredSkills: ['Python', 'TensorFlow', 'PyTorch', 'Machine Learning', 'Deep Learning', 'Mathematics']
  },
  {
    id: 'data-scientist',
    name: 'Data Scientist',
    icon: '📊',
    domain: 'Data',
    description: 'Chuyên gia phân tích dữ liệu để khám phá insights và hỗ trợ ra quyết định kinh doanh. Sử dụng thống kê, machine learning và visualization.',
    matchScore: 0.88,
    growthRate: 0.87,
    competition: 0.78,
    aiRelevance: 0.85,
    requiredSkills: ['Python', 'R', 'SQL', 'Statistics', 'Machine Learning', 'Data Visualization']
  },
  {
    id: 'software-engineer',
    name: 'Software Engineer',
    icon: '💻',
    domain: 'Software',
    description: 'Kỹ sư phần mềm thiết kế và phát triển các ứng dụng, hệ thống phần mềm. Làm việc với nhiều ngôn ngữ lập trình và công nghệ khác nhau.',
    matchScore: 0.82,
    growthRate: 0.81,
    competition: 0.75,
    aiRelevance: 0.55,
    requiredSkills: ['Programming', 'Data Structures', 'Algorithms', 'Git', 'Testing']
  },
  {
    id: 'ui-ux-designer',
    name: 'UI/UX Designer',
    icon: '🎨',
    domain: 'Design',
    description: 'Thiết kế trải nghiệm người dùng và giao diện sản phẩm số. Kết hợp nghiên cứu người dùng, wireframing, prototyping và visual design.',
    matchScore: 0.79,
    growthRate: 0.73,
    competition: 0.72,
    aiRelevance: 0.45,
    requiredSkills: ['Figma', 'Adobe XD', 'User Research', 'Prototyping', 'Visual Design']
  },
  {
    id: 'product-manager',
    name: 'Product Manager',
    icon: '📱',
    domain: 'Business',
    description: 'Quản lý sản phẩm từ ý tưởng đến ra mắt thị trường. Làm việc với các team khác nhau để đảm bảo sản phẩm đáp ứng nhu cầu người dùng.',
    matchScore: 0.75,
    growthRate: 0.78,
    competition: 0.83,
    aiRelevance: 0.68,
    requiredSkills: ['Product Strategy', 'Agile', 'Analytics', 'Communication', 'Roadmapping']
  },
  {
    id: 'backend-developer',
    name: 'Backend Developer',
    icon: '⚙️',
    domain: 'Software',
    description: 'Phát triển phần backend của ứng dụng, xử lý logic nghiệp vụ, database và API. Đảm bảo hiệu năng và bảo mật hệ thống.',
    matchScore: 0.81,
    growthRate: 0.79,
    competition: 0.71,
    aiRelevance: 0.58,
    requiredSkills: ['Node.js', 'Python', 'Java', 'SQL', 'API Design', 'Docker']
  },
  {
    id: 'frontend-developer',
    name: 'Frontend Developer',
    icon: '🌐',
    domain: 'Software',
    description: 'Xây dựng giao diện người dùng cho web và mobile. Làm việc với HTML, CSS, JavaScript và các framework hiện đại.',
    matchScore: 0.77,
    growthRate: 0.76,
    competition: 0.74,
    aiRelevance: 0.42,
    requiredSkills: ['React', 'JavaScript', 'HTML', 'CSS', 'TypeScript', 'Responsive Design']
  },
  {
    id: 'devops-engineer',
    name: 'DevOps Engineer',
    icon: '🔧',
    domain: 'Cloud',
    description: 'Quản lý infrastructure, CI/CD pipeline và automation. Đảm bảo hệ thống luôn stable và scalable.',
    matchScore: 0.73,
    growthRate: 0.84,
    competition: 0.69,
    aiRelevance: 0.52,
    requiredSkills: ['Docker', 'Kubernetes', 'AWS', 'CI/CD', 'Linux', 'Terraform']
  }
];