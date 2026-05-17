import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { User, Palette, Ruler, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function Profile() {
  const { logout, username, profilePicture } = useAuth();
  const [profileData, setProfileData] = useState({
    username: '',
    profilePicture: '',
    bodyShape: '',
    skinTone: ''
  });

  useEffect(() => {
    // Load data from localStorage or API
    const storedBodyShape = localStorage.getItem('style_engine_body_shape') || 'Not set';
    const storedSkinTone = localStorage.getItem('style_engine_skin_tone') || 'Not set';
    
    setProfileData({
      username: username || localStorage.getItem('username') || 'User',
      profilePicture: profilePicture || localStorage.getItem('style_engine_profile_picture') || '',
      bodyShape: storedBodyShape,
      skinTone: storedSkinTone
    });
  }, [username, profilePicture]);

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-indigo-500 to-purple-600">My Profile</h1>
        <p className="text-zinc-500 mt-1 text-lg">Manage your personal information and preferences.</p>
      </div>

      <Card className="border-0 shadow-xl overflow-hidden bg-white/60 backdrop-blur-xl ring-1 ring-black/5">
        <div className="bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 h-40"></div>
        <CardContent className="pt-6 px-8 pb-10">
          <div className="flex flex-col sm:flex-row items-center sm:items-end gap-6 -mt-24 sm:-mt-28 mb-10 relative z-10">
            <div className="w-32 h-32 sm:w-36 sm:h-36 bg-white/80 backdrop-blur-md rounded-2xl p-2 shadow-lg shrink-0 transform rotate-3 hover:rotate-0 transition-transform duration-300">
              {profileData.profilePicture ? (
                <img src={profileData.profilePicture} alt="Profile" className="w-full h-full rounded-xl object-cover" />
              ) : (
                <div className="w-full h-full bg-gradient-to-tr from-indigo-100 to-purple-100 rounded-xl flex items-center justify-center">
                  <User className="w-14 h-14 text-indigo-400" />
                </div>
              )}
            </div>
            
            <div className="flex flex-col items-center sm:items-start pb-2 sm:pb-4">
              <h2 className="text-3xl sm:text-4xl font-black text-zinc-900 tracking-tight">{profileData.username}</h2>
              <p className="text-indigo-600 font-semibold tracking-wide uppercase text-sm mt-1">GRWM Member</p>
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <div className="flex items-start gap-5 p-5 rounded-2xl bg-white/80 backdrop-blur-sm border border-zinc-100 shadow-sm hover:shadow-md transition-shadow group">
              <div className="p-3 bg-indigo-50 rounded-xl shadow-inner group-hover:scale-110 transition-transform">
                <Ruler className="w-6 h-6 text-indigo-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-zinc-500">Body Shape</p>
                <p className="text-lg font-semibold text-zinc-900 capitalize">{profileData.bodyShape}</p>
              </div>
            </div>

            <div className="flex items-start gap-5 p-5 rounded-2xl bg-white/80 backdrop-blur-sm border border-zinc-100 shadow-sm hover:shadow-md transition-shadow group">
              <div className="p-3 bg-purple-50 rounded-xl shadow-inner group-hover:scale-110 transition-transform">
                <Palette className="w-6 h-6 text-purple-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-zinc-500">Skin Tone</p>
                <div className="flex items-center gap-2 mt-1">
                  {profileData.skinTone !== 'Not set' && (
                    <div 
                      className="w-5 h-5 rounded-full border border-zinc-200 shadow-inner shrink-0" 
                      style={{ backgroundColor: profileData.skinTone }}
                    />
                  )}
                  <p className="text-lg font-semibold text-zinc-900 uppercase">
                    {profileData.skinTone !== 'Not set' ? profileData.skinTone : 'Not set'}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-12 pt-8 border-t border-zinc-200/60">
            <Button 
              variant="outline" 
              className="w-full sm:w-auto rounded-xl text-zinc-600 hover:text-red-700 hover:bg-red-50 border-zinc-200 hover:border-red-200 transition-colors h-11 px-8"
              onClick={logout}
            >
              <LogOut className="w-4 h-4 mr-2" />
              Sign Out Securely
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
