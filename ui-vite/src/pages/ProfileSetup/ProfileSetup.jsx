// src/pages/ProfileSetup/ProfileSetup.jsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../components/common/Button/Button';
import Input from '../../components/common/Input/Input';
import Card from '../../components/common/Card/Card';
import Badge from '../../components/common/Badge/Badge';
import { analyzeProfile } from '../../services/api';
import styles from './ProfileSetup.module.css';

export default function ProfileSetup() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [errors, setErrors] = useState({});
  const [formData, setFormData] = useState({
    fullName: '',
    age: '',
    education: '',
    interests: [],
    skills: '',
    careerGoal: ''
  });

  const interestOptions = [
    'IT', 'Công nghệ', 'Thiết kế', 'Kinh doanh', 
    'Marketing', 'Khoa học', 'Nghệ thuật', 'Giáo dục',
    'Y tế', 'Kỹ thuật', 'Tài chính', 'Truyền thông'
  ];

  const educationOptions = [
    'THPT', 'Cao đẳng', 'Đại học', 'Thạc sĩ', 'Tiến sĩ'
  ];

  const getErrorsForStep = (stepValue = step) => {
    const nextErrors = {};
    const fullName = formData.fullName.trim();
    const ageValue = Number(formData.age);
    const skills = formData.skills.trim();
    const careerGoal = formData.careerGoal.trim();

    if (stepValue === 1) {
      if (fullName.length < 2) nextErrors.fullName = 'Vui lòng nhập họ tên hợp lệ.';
      if (!Number.isFinite(ageValue) || ageValue < 12 || ageValue > 99) {
        nextErrors.age = 'Tuổi phải từ 12 đến 99.';
      }
      if (!formData.education) nextErrors.education = 'Vui lòng chọn trình độ học vấn.';
    }

    if (stepValue === 2) {
      if (!formData.interests.length) nextErrors.interests = 'Vui lòng chọn ít nhất một lĩnh vực.';
    }

    if (stepValue === 3) {
      if (skills.length < 3) nextErrors.skills = 'Vui lòng mô tả kỹ năng của bạn.';
      if (careerGoal.length < 3) nextErrors.careerGoal = 'Vui lòng mô tả mục tiêu nghề nghiệp.';
    }

    return nextErrors;
  };

  const validateCurrentStep = () => {
    const nextErrors = getErrorsForStep();
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleInterestToggle = (interest) => {
    setFormData(prev => ({
      ...prev,
      interests: prev.interests.includes(interest)
        ? prev.interests.filter(i => i !== interest)
        : [...prev.interests, interest]
    }));
  };

  const handleSubmit = async () => {
    if (!validateCurrentStep()) return;

    setIsSubmitting(true);
    setSubmitError('');

    const payload = {
      personalInfo: {
        fullName: formData.fullName.trim(),
        age: formData.age,
        education: formData.education
      },
      interests: formData.interests,
      skills: formData.skills.trim(),
      careerGoal: formData.careerGoal.trim(),
      chatHistory: []
    };

    try {
      const processedProfile = await analyzeProfile(payload);
      localStorage.setItem('userProfile', JSON.stringify(formData));
      localStorage.setItem('processedProfile', JSON.stringify(processedProfile));
      navigate('/assessment');
    } catch (error) {
      setSubmitError('Kh?ng th? k?t n?i API. Vui l?ng th? l?i.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isStepValid = () => Object.keys(getErrorsForStep()).length === 0;

  return (
    <div className={styles.container}>
      <div className="container">
        <div className={styles.content}>
          {/* Progress */}
          <div className={styles.progress}>
            <div className={styles.progressSteps}>
              {[1, 2, 3].map(s => (
                <div 
                  key={s} 
                  className={`${styles.progressStep} ${s <= step ? styles.active : ''}`}
                >
                  <div className={styles.stepNumber}>{s}</div>
                  <div className={styles.stepLabel}>
                    {s === 1 ? 'Thông tin' : s === 2 ? 'Sở thích' : 'Mục tiêu'}
                  </div>
                </div>
              ))}
            </div>
            <div className={styles.progressBar}>
              <div 
                className={styles.progressFill} 
                style={{ width: `${(step / 3) * 100}%` }}
              />
            </div>
          </div>

          {/* Form */}
          <Card>
            <div className={styles.form}>
              {step === 1 && (
                <div className={styles.stepContent}>
                  <h2 className={styles.stepTitle}>Thông tin cơ bản</h2>
                  <p className={styles.stepDescription}>
                    Cho chúng tôi biết thêm về bạn
                  </p>

                  <div className={styles.fields}>
                    <Input
                      label="Họ và tên"
                      placeholder="Nguyễn Văn A"
                      value={formData.fullName}
                      onChange={(e) => setFormData({...formData, fullName: e.target.value})}
                    />

                    <Input
                      label="Tuổi"
                      type="number"
                      placeholder="20"
                      value={formData.age}
                      onChange={(e) => setFormData({...formData, age: e.target.value})}
                    />

                    <div className={styles.field}>
                      <label className={styles.label}>Trình độ học vấn</label>
                      <div className={styles.options}>
                        {educationOptions.map(edu => (
                          <button
                            key={edu}
                            className={`${styles.option} ${formData.education === edu ? styles.selected : ''}`}
                            onClick={() => setFormData({...formData, education: edu})}
                          >
                            {edu}
                          </button>
                        ))}
                      </div>
                      {errors.education && (
                        <div className={styles.fieldError}>{errors.education}</div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {step === 2 && (
                <div className={styles.stepContent}>
                  <h2 className={styles.stepTitle}>Sở thích của bạn</h2>
                  <p className={styles.stepDescription}>
                    Chọn các lĩnh vực bạn quan tâm (có thể chọn nhiều)
                  </p>

                  <div className={styles.interestGrid}>
                    {interestOptions.map(interest => (
                      <button
                        key={interest}
                        className={`${styles.interestCard} ${
                          formData.interests.includes(interest) ? styles.selected : ''
                        }`}
                        onClick={() => handleInterestToggle(interest)}
                      >
                        <span className={styles.interestEmoji}>
                          {interest === 'IT' ? '💻' : 
                           interest === 'Thiết kế' ? '🎨' :
                           interest === 'Kinh doanh' ? '💼' :
                           interest === 'Marketing' ? '📱' :
                           interest === 'Khoa học' ? '🔬' : '📚'}
                        </span>
                        <span className={styles.interestName}>{interest}</span>
                        {formData.interests.includes(interest) && (
                          <span className={styles.checkmark}>✓</span>
                        )}
                      </button>
                    ))}
                  </div>

                  <div className={styles.selectedCount}>
                    Đã chọn: {formData.interests.length} lĩnh vực
                  </div>
                </div>
              )}

              {step === 3 && (
                <div className={styles.stepContent}>
                  <h2 className={styles.stepTitle}>Kỹ năng & Mục tiêu</h2>
                  <p className={styles.stepDescription}>
                    Chia sẻ về kỹ năng và định hướng nghề nghiệp
                  </p>

                  <div className={styles.fields}>
                    <div className={styles.field}>
                      <label className={styles.label}>Kỹ năng hiện tại</label>
                      <textarea
                        className={styles.textarea}
                        placeholder="Ví dụ: Lập trình Python, thiết kế UI/UX, quản lý dự án..."
                        value={formData.skills}
                        onChange={(e) => setFormData({...formData, skills: e.target.value})}
                        rows={4}
                      />
                    </div>

                    <div className={styles.field}>
                      <label className={styles.label}>Mục tiêu nghề nghiệp</label>
                      <textarea
                        className={styles.textarea}
                        placeholder="Ví dụ: Tôi muốn trở thành AI Engineer, làm việc với dữ liệu và machine learning..."
                        value={formData.careerGoal}
                        onChange={(e) => setFormData({...formData, careerGoal: e.target.value})}
                        rows={4}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className={styles.actions}>
                {submitError && (
                  <div className={styles.error}>{submitError}</div>
                )}
                {step > 1 && (
                  <Button 
                    variant="outline" 
                    onClick={() => setStep(step - 1)}
                  >
                    Quay lại
                  </Button>
                )}
                
                {step < 3 ? (
                  <Button 
                    onClick={() => { if (validateCurrentStep()) setStep(step + 1); }}
                    disabled={!isStepValid()}
                    fullWidth={step === 1}
                  >
                    Tiếp tục
                  </Button>
                ) : (
                  <Button 
                    onClick={handleSubmit}
                    disabled={!isStepValid() || isSubmitting}
                    fullWidth
                  >
                    {isSubmitting ? 'Đang xử lý...' : 'Hoàn thành'}
                  </Button>
                )}
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
