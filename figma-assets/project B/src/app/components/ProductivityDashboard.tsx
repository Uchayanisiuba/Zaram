import React from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Progress } from './ui/progress';
import { Badge } from './ui/badge';
import { TrendingUp, Calendar, Clock, Target, BarChart3, Activity, Users, Zap } from 'lucide-react';
import exampleImage from 'figma:asset/b638caa0ba09a47b99268eb04825697fe72fd1c4.png';

export function ProductivityDashboard() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-400 via-purple-500 to-purple-600 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Main Content Area - Computer Monitor Effect */}
        <div className="relative">
          {/* Monitor Frame */}
          <div className="bg-gray-900 rounded-t-2xl p-6 shadow-2xl transform perspective-1000 rotateX-5">
            {/* Monitor Header */}
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center space-x-3">
                <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                <div className="w-3 h-3 bg-green-500 rounded-full"></div>
              </div>
              <div className="text-gray-400 text-sm">Dashboard</div>
            </div>

            {/* Dashboard Content */}
            <div className="space-y-8">
              {/* Hero Section */}
              <div className="text-center space-y-4">
                <h1 className="text-4xl text-white mb-2">
                  You're on a wave of
                </h1>
                <h1 className="text-4xl text-white mb-6">
                  productivity!
                </h1>
                <p className="text-gray-300 text-lg">
                  Keep up the momentum with your daily tasks and goals
                </p>
              </div>

              {/* Main Dashboard Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {/* Today's Focus Card */}
                <Card className="bg-gray-800/50 border-gray-700 backdrop-blur-sm p-6">
                  <div className="flex items-center justify-between mb-4">
                    <Target className="w-5 h-5 text-blue-400" />
                    <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">
                      Active
                    </Badge>
                  </div>
                  <h3 className="text-white text-lg mb-2">Today's Focus</h3>
                  <p className="text-2xl text-white mb-2">4</p>
                  <p className="text-gray-400 text-sm">Tasks completed</p>
                  <Progress value={75} className="mt-3" />
                </Card>

                {/* Time Tracking Card */}
                <Card className="bg-gray-800/50 border-gray-700 backdrop-blur-sm p-6">
                  <div className="flex items-center justify-between mb-4">
                    <Clock className="w-5 h-5 text-green-400" />
                    <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                      Running
                    </Badge>
                  </div>
                  <h3 className="text-white text-lg mb-2">Time Tracked</h3>
                  <p className="text-2xl text-white mb-2">6h 24m</p>
                  <p className="text-gray-400 text-sm">Today's total</p>
                  <div className="mt-3 flex items-center text-green-400 text-sm">
                    <TrendingUp className="w-4 h-4 mr-1" />
                    +12% vs yesterday
                  </div>
                </Card>

                {/* Weekly Goals Card */}
                <Card className="bg-gray-800/50 border-gray-700 backdrop-blur-sm p-6">
                  <div className="flex items-center justify-between mb-4">
                    <Calendar className="w-5 h-5 text-purple-400" />
                    <Badge className="bg-purple-500/20 text-purple-400 border-purple-500/30">
                      Week 32
                    </Badge>
                  </div>
                  <h3 className="text-white text-lg mb-2">Weekly Goal</h3>
                  <p className="text-2xl text-white mb-2">67</p>
                  <p className="text-gray-400 text-sm">% Complete</p>
                  <Progress value={67} className="mt-3" />
                </Card>

                {/* Productivity Score Card */}
                <Card className="bg-gray-800/50 border-gray-700 backdrop-blur-sm p-6">
                  <div className="flex items-center justify-between mb-4">
                    <Activity className="w-5 h-5 text-orange-400" />
                    <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30">
                      High
                    </Badge>
                  </div>
                  <h3 className="text-white text-lg mb-2">Productivity</h3>
                  <p className="text-2xl text-white mb-2">74</p>
                  <p className="text-gray-400 text-sm">Score today</p>
                  <div className="mt-3 flex items-center text-orange-400 text-sm">
                    <TrendingUp className="w-4 h-4 mr-1" />
                    Peak performance
                  </div>
                </Card>
              </div>

              {/* Secondary Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Recent Activity */}
                <Card className="bg-gray-800/50 border-gray-700 backdrop-blur-sm p-6 lg:col-span-2">
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="text-white text-lg">Recent Activity</h3>
                    <BarChart3 className="w-5 h-5 text-gray-400" />
                  </div>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                        <span className="text-gray-300">Completed design review</span>
                      </div>
                      <span className="text-gray-500 text-sm">2 min ago</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                        <span className="text-gray-300">Updated project documentation</span>
                      </div>
                      <span className="text-gray-500 text-sm">15 min ago</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-2 h-2 bg-purple-400 rounded-full"></div>
                        <span className="text-gray-300">Team meeting completed</span>
                      </div>
                      <span className="text-gray-500 text-sm">1 hour ago</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-2 h-2 bg-orange-400 rounded-full"></div>
                        <span className="text-gray-300">Code review feedback</span>
                      </div>
                      <span className="text-gray-500 text-sm">2 hours ago</span>
                    </div>
                  </div>
                </Card>

                {/* Quick Actions */}
                <Card className="bg-gray-800/50 border-gray-700 backdrop-blur-sm p-6">
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="text-white text-lg">Quick Actions</h3>
                    <Zap className="w-5 h-5 text-yellow-400" />
                  </div>
                  <div className="space-y-3">
                    <Button className="w-full bg-blue-600 hover:bg-blue-500 text-white">
                      Start Timer
                    </Button>
                    <Button className="w-full bg-gray-700 hover:bg-gray-600 text-white">
                      Add Task
                    </Button>
                    <Button className="w-full bg-gray-700 hover:bg-gray-600 text-white">
                      View Calendar
                    </Button>
                    <Button className="w-full bg-gray-700 hover:bg-gray-600 text-white">
                      Team Chat
                    </Button>
                  </div>
                </Card>
              </div>

              {/* Bottom Status Bar */}
              <div className="flex items-center justify-between pt-6 border-t border-gray-700">
                <div className="flex items-center space-x-6">
                  <div className="flex items-center space-x-2 text-gray-400">
                    <Users className="w-4 h-4" />
                    <span className="text-sm">3 team members online</span>
                  </div>
                  <div className="flex items-center space-x-2 text-gray-400">
                    <Activity className="w-4 h-4" />
                    <span className="text-sm">All systems operational</span>
                  </div>
                </div>
                <div className="text-gray-500 text-sm">
                  Last updated: just now
                </div>
              </div>
            </div>
          </div>

          {/* Monitor Stand */}
          <div className="bg-gray-700 h-8 w-32 mx-auto rounded-b-lg shadow-lg"></div>
          <div className="bg-gray-800 h-4 w-48 mx-auto rounded-lg shadow-lg"></div>
        </div>

        {/* Bottom Text */}
        <div className="text-center mt-12">
          <h2 className="text-white text-3xl mb-4">Aarav</h2>
          <p className="text-purple-200 text-lg">
            Your AI-powered productivity companion
          </p>
        </div>
      </div>
    </div>
  );
}